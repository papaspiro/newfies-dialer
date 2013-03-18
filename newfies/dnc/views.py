#
# Newfies-Dialer License
# http://www.newfies-dialer.org
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2011-2013 Star2Billing S.L.
#
# The Initial Developer of the Original Code is
# Arezqui Belaid <info@star2billing.com>
#
from django.contrib.auth.decorators import login_required, \
    permission_required
from django.http import HttpResponseRedirect, HttpResponse, \
    Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.utils.translation import ugettext as _
from django.db.models import Q
from django.db.models import Count
from dnc.models import DNC, DNCContact
from dnc.forms import DNCForm#, Contact_fileImport, \
#    PhonebookForm, ContactForm
from dnc.constants import DNC_COLUMN_NAME, DNC_CONTACT_COLUMN_NAME
from dialer_campaign.function_def import check_dialer_setting,\
    dialer_setting_limit, user_dialer_setting_msg

from frontend_notification.views import frontend_send_notification
from common.common_functions import striplist, current_view,\
    get_pagination_vars
import csv
import json


@permission_required('dnc.view_dnc_list', login_url='/')
@login_required
def dnc_list(request):
    """Phonebook list for the logged in user

    **Attributes**:

        * ``template`` - frontend/dnc_list/list.html

    **Logic Description**:

        * List all dnc which belong to the logged in user.
    """
    sort_col_field_list = ['id', 'name', 'updated_date']
    default_sort_field = 'id'
    pagination_data = \
        get_pagination_vars(request, sort_col_field_list, default_sort_field)

    PAGE_SIZE = pagination_data['PAGE_SIZE']
    sort_order = pagination_data['sort_order']

    dnc_list = DNC.objects\
        .filter(user=request.user).order_by(sort_order)

    template = 'frontend/dnc_list/list.html'
    data = {
        'module': current_view(request),
        'msg': request.session.get('msg'),
        'dnc_list': dnc_list,
        'total_dnc': dnc_list.count(),
        'PAGE_SIZE': PAGE_SIZE,
        'DNC_COLUMN_NAME': DNC_COLUMN_NAME,
        'col_name_with_order': pagination_data['col_name_with_order'],
        'dialer_setting_msg': user_dialer_setting_msg(request.user),
    }
    request.session['msg'] = ''
    request.session['error_msg'] = ''
    return render_to_response(template, data,
                              context_instance=RequestContext(request))


@permission_required('dnc.add_dnc', login_url='/')
@login_required
def dnc_add(request):
    """Add new DNC for the logged in user

    **Attributes**:

        * ``form`` - DNCForm
        * ``template`` - frontend/dnc_list/change.html

    **Logic Description**:

        * Add a new DNC which will belong to the logged in user
          via the DNCForm & get redirected to the dnc list
    """
    form = DNCForm()
    if request.method == 'POST':
        form = DNCForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            request.session["msg"] = _('"%(name)s" added.') %\
                {'name': request.POST['name']}
            return HttpResponseRedirect('/dnc/')
    template = 'frontend/dnc_list/change.html'
    data = {
        'module': current_view(request),
        'form': form,
        'action': 'add',
        'dialer_setting_msg': user_dialer_setting_msg(request.user),
    }
    return render_to_response(template, data,
                              context_instance=RequestContext(request))

@login_required
def get_dnc_contact_count(request):
    """To get total no of dnc contacts belonging to a dnc list"""
    values = request.GET.getlist('ids')
    values = ", ".join(["%s" % el for el in values])
    contact_count = DNCContact.objects.filter(dnc__user=request.user)\
        .extra(where=['dnc_id IN (%s)' % values]).count()

    return HttpResponse(contact_count)


@permission_required('dnc.delete_dnc', login_url='/')
@login_required
def dnc_del(request, object_id):
    """Delete a dnc for a logged in user

    **Attributes**:

        * ``object_id`` - Selected dnc object
        * ``object_list`` - Selected dnc objects

    **Logic Description**:

        * Delete contacts from a contact list belonging to a dnc list.
        * Delete selected the dnc from the dnc list
    """
    if int(object_id) != 0:
        # When object_id is not 0
        dnc = get_object_or_404(
            DNC, pk=object_id, user=request.user)

        # 1) delete all contacts belonging to a dnc
        dnc_contact_list = DNCContact.objects.filter(dnc=dnc)
        dnc_contact_list.delete()

        # 2) delete dnc
        request.session["msg"] = _('"%(name)s" is deleted.')\
            % {'name': dnc.name}
        dnc.delete()
    else:
        # When object_id is 0 (Multiple records delete)
        values = request.POST.getlist('select')
        values = ", ".join(["%s" % el for el in values])
        try:
            # 1) delete all contacts belonging to a phonebook
            dnc_contact_list = DNCContact.objects\
                .filter(dnc__user=request.user)\
                .extra(where=['dnc_id IN (%s)' % values])
            if dnc_contact_list:
                dnc_contact_list.delete()

            # 2) delete dnc
            dnc_list = DNC.objects.filter(user=request.user)\
                .extra(where=['id IN (%s)' % values])
            if dnc_list:
                request.session["msg"] =\
                    _('%(count)s dnc list(s) are deleted.')\
                    % {'count': dnc_list.count()}
                dnc_list.delete()
        except:
            raise Http404

    return HttpResponseRedirect('/dnc/')


@permission_required('dnc.change_dnc', login_url='/')
@login_required
def dnc_change(request, object_id):
    """Update/Delete DNC for the logged in user

    **Attributes**:

        * ``object_id`` - Selected dnc object
        * ``form`` - DNCForm
        * ``template`` - frontend/dnc_list/change.html

    **Logic Description**:

        * Update/delete selected dnc from the dnc list
          via DNCForm & get redirected to dnc list
    """
    dnc = get_object_or_404(DNC, pk=object_id, user=request.user)
    form = DNCForm(instance=dnc)
    if request.method == 'POST':
        if request.POST.get('delete'):
            dnc_del(request, object_id)
            return HttpResponseRedirect('/dnc/')
        else:
            form = DNCForm(request.POST, instance=dnc)
            if form.is_valid():
                form.save()
                request.session["msg"] = _('"%(name)s" is updated.') \
                    % {'name': request.POST['name']}
                return HttpResponseRedirect('/dnc/')

    template = 'frontend/dnc_list/change.html'
    data = {
        'module': current_view(request),
        'form': form,
        'action': 'update',
        'dialer_setting_msg': user_dialer_setting_msg(request.user),
    }
    return render_to_response(template, data,
                              context_instance=RequestContext(request))

