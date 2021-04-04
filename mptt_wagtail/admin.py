import json

from django import forms, http
from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.admin.options import get_content_type_for_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils.html import format_html
from django.utils.translation import gettext as _
from js_asset import JS
from mptt.exceptions import InvalidMove
from wagtail.contrib.modeladmin.options import ModelAdmin


class WagtailDraggableMPTTAdmin(ModelAdmin):

    list_display = ("tree_actions", "indented_title")
    list_per_page = 2000  # This will take a really long time to load.
    mptt_level_indent = 20
    expand_tree_by_default = False

    def tree_actions(self, item):
        try:
            url = item.get_absolute_url()
        except Exception:  # Nevermind.
            url = ""

        return format_html(
            '<div class="drag-handle"></div>'
            '<div class="tree-node" data-pk="{}" data-level="{}"'
            ' data-url="{}"></div>',
            item.pk,
            item._mpttfield("level"),
            url,
        )

    tree_actions.short_description = ""

    def indented_title(self, item):
        """
        Generate a short title for an object, indent it depending on
        the object's depth in the hierarchy.
        """

        return format_html(
            '<div style="text-indent:{}px;text-align:left;font-weight:normal">{}</div>',
            item._mpttfield("level") * self.mptt_level_indent,
            item,
        )

    indented_title.short_description = "title"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if (
            issubclass(db_field.remote_field.model, MPTTModel)
            and not isinstance(db_field, TreeForeignKey)
            and db_field.name not in self.raw_id_fields
        ):
            db = kwargs.get("using")

            limit_choices_to = db_field.get_limit_choices_to()
            defaults = dict(
                form_class=TreeNodeChoiceField,
                queryset=db_field.remote_field.model._default_manager.using(
                    db
                ).complex_filter(limit_choices_to),
                required=False,
            )
            defaults.update(kwargs)
            kwargs = defaults
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_ordering(self, request):
        """
        Changes the default ordering for changelists to tree-order.
        """
        mptt_opts = self.model._mptt_meta
        return self.ordering or (mptt_opts.tree_id_attr, mptt_opts.left_attr)

    def index_view(self, request):

        if request.is_ajax() and request.POST.get("cmd") == "move_node":
            return self._move_node(request)

        response = super().index_view(request)

        try:
            response.context_data["media"] = forms.Media(
                css={"all": ["mptt/draggable-admin.css"]},
                js=[
                    "admin/js/vendor/jquery/jquery.js",
                    "admin/js/jquery.init.js",
                    JS(
                        "mptt/draggable-admin.js",
                        {
                            "id": "draggable-admin-context",
                            "data-context": json.dumps(
                                self._tree_context(request), cls=DjangoJSONEncoder
                            ),
                        },
                    ),
                ],
            )

        except (AttributeError, KeyError):
            # Not meant for us if there is no context_data attribute (no
            # TemplateResponse) or no media in the context.
            pass

        return response

    def get_data_before_update(self, request, cut_item, pasted_on):
        mptt_opts = self.model._mptt_meta
        mptt_attr_fields = (
            "parent_attr",
            "left_attr",
            "right_attr",
            "tree_id_attr",
            "level_attr",
        )
        mptt_fields = [getattr(mptt_opts, attr) for attr in mptt_attr_fields]
        return {k: getattr(cut_item, k) for k in mptt_fields}

    def get_move_node_change_message(
        self, request, cut_item, pasted_on, data_before_update
    ):
        changed_fields = [
            k for k, v in data_before_update.items() if v != getattr(cut_item, k)
        ]
        return [{"changed": {"fields": changed_fields}}]

    @transaction.atomic
    def _move_node(self, request):
        position = request.POST.get("position")
        if position not in ("last-child", "left", "right"):
            messages.error(request, _("Did not understand moving instruction."))
            return http.HttpResponse("FAIL, unknown instruction.")

        queryset = self.get_queryset(request)

        try:
            cut_item = queryset.get(pk=request.POST.get("cut_item"))

            pasted_on = queryset.get(pk=request.POST.get("pasted_on"))
        except (self.model.DoesNotExist, TypeError, ValueError):
            messages.error(request, _("Objects have disappeared, try again."))
            return http.HttpResponse("FAIL, invalid objects.")

        model_name = cut_item.__class__.__name__.lower()
        if not request.user.has_perms(model_name + ".can_change_" + model_name):
            messages.error(request, _("No permission."))
            return http.HttpResponse("FAIL, no permission.")

        data_before_update = self.get_data_before_update(request, cut_item, pasted_on)

        try:
            self.model._tree_manager.move_node(cut_item, pasted_on, position)
        except InvalidMove as e:
            messages.error(request, "%s" % e)
            return http.HttpResponse("FAIL, invalid move.")
        except IntegrityError as e:
            messages.error(request, _("Database error: %s") % e)

            raise

        change_message = self.get_move_node_change_message(
            request, cut_item, pasted_on, data_before_update
        )

        LogEntry.objects.log_action(
            user_id=request.user.id,
            content_type_id=get_content_type_for_model(cut_item).pk,
            object_id=cut_item.pk,
            object_repr=str(cut_item),
            action_flag=CHANGE,
            change_message=change_message,
        )
        messages.success(request, "%s has been successfully moved." % cut_item)
        return http.HttpResponse("OK, moved.")

    def _build_tree_structure(self, queryset):
        """
        Build an in-memory representation of the item tree, trying to keep
        database accesses down to a minimum. The returned dictionary looks like
        this (as json dump):

            {"6": [7, 8, 10]
             "7": [12],
             ...
             }

        Leaves are not included in the dictionary.
        """
        all_nodes = {}

        mptt_opts = self.model._mptt_meta
        items = queryset.values_list("pk", "%s_id" % mptt_opts.parent_attr)
        for p_id, parent_id in items:
            all_nodes.setdefault(str(parent_id) if parent_id else 0, []).append(p_id)
        return all_nodes

    def _tree_context(self, request):
        opts = self.model._meta

        return {
            "storageName": "tree_%s_%s_collapsed" % (opts.app_label, opts.model_name),
            "treeStructure": self._build_tree_structure(self.get_queryset(request)),
            "levelIndent": self.mptt_level_indent,
            "messages": {
                "before": ("move node before node"),
                "child": ("move node to child position"),
                "after": ("move node after node"),
                "collapseTree": ("Collapse tree"),
                "expandTree": ("Expand tree"),
            },
            "expandTreeByDefault": self.expand_tree_by_default,
        }
