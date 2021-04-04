from django.template import Library
from django.utils.safestring import mark_safe

register = Library()


@register.inclusion_tag(
    "modeladmin/includes/result_row_value.html", takes_context=True)
def customize_result_row_value_display(context, index):
    add_action_buttons = False
    item = context['item']
    closing_tag = mark_safe(item[-5:])
    request = context['request']
    model_admin = context['view'].model_admin
    field_name = model_admin.get_list_display(request)[index]
    
    ######## update
    if item.__contains__('class="field-indented_title"'):
        item = mark_safe(item.replace('<td ','<th style="padding-top: 1.2em;padding-right: 1em;padding-bottom: 1.2em;padding-left: 1em;text-align:left"'))
        item = mark_safe(item.replace('</td>','</th>'))
    ########
    
    if field_name == model_admin.get_list_display_add_buttons(request):
        add_action_buttons = True
        item = mark_safe(item[0:-5])
       
    context.update({
        'item': item,
        'add_action_buttons': add_action_buttons,
        'closing_tag': closing_tag,
    })
    return context
