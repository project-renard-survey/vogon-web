"""
Provides :class:`.RelationTemplate`\-related views.
"""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.db import transaction, DatabaseError
from django.forms import formset_factory
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from string import Formatter

from annotations.forms import (RelationTemplatePartFormSet,
                               RelationTemplatePartForm,
                               RelationTemplateForm)
from annotations.models import *
from annotations import relations
from concepts.models import Concept, Type
from annotations.serializers import ConceptSerializer, AppellationSerializer, TemplatePartSerializer, TemplateSerializer, RelationSerializer

import copy
import json
import logging
import networkx as nx
import pdb

logger = logging.getLogger(__name__)
logger.setLevel('ERROR')


@staff_member_required
def add_relationtemplate(request):
    """
    Staff can use this view to create :class:`.RelationTemplate`\s.

    Parameters
    ----------
    project_id : int
    request : `django.http.requests.HttpRequest`

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    formset = formset_factory(RelationTemplatePartForm,
                              formset=RelationTemplatePartFormSet)
    form_class = RelationTemplateForm   # e.g. Name, Description.

    context = {}

    if request.POST:
        logger.debug('add_relationtemplate: post request')
        
        # Instatiate both form(set)s with data.
        relationtemplatepart_formset = formset(request.POST, prefix='parts')
        relationtemplate_form = form_class(request.POST)
        context['formset'] = relationtemplatepart_formset
        context['templateform'] = relationtemplate_form

        formset_is_valid = relationtemplatepart_formset.is_valid()
        form_is_valid = relationtemplate_form.is_valid()
        
        if formset_is_valid and form_is_valid:
            relationtemplate_data = dict(relationtemplate_form.cleaned_data)
            relationtemplate_data['createdBy'] = request.user
            part_data = [dict(form.cleaned_data) for form in relationtemplatepart_formset]

            try:
                # relations.create_template() calls validation methods.
                template = relations.create_template(relationtemplate_data, part_data)
                return HttpResponseRedirect(reverse('get_relationtemplate',
                                            args=(template.id,)))
            except relations.InvalidTemplate as E:
                relationtemplate_form.add_error(None, E.message)
                logger.debug('creating relationtemplate failed: %s' % (E.message))
        context['formset'] = relationtemplatepart_formset
        context['templateform'] = relationtemplate_form

    else:   # No data, start with a fresh formset.
        context['formset'] = formset(prefix='parts')
        context['templateform'] = form_class()

    return render(request, 'annotations/relationtemplate.html', context)


@login_required
def list_relationtemplate(request):
    """
    Returns a list of all :class:`.RelationTemplate`\s.

    This view will return JSON if ``format=json`` is passed in the GET request.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """
    queryset = RelationTemplate.objects.all()
    search = request.GET.get('search', None)
    all_templates = request.GET.get('all', False)
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )
    if not all_templates:
        queryset = queryset.filter(createdBy=request.user)

    data = {
        'templates': [{
            'id': rt.id,
            'name': rt.name,
            'description': rt.description,
            'fields': relations.get_fields(rt),
            } for rt in queryset.order_by('-id')]
        }
    response_format = request.GET.get('format', None)
    if response_format == 'json':
        return JsonResponse(data)

    template = "annotations/relationtemplate_list.html"
    context = {
        'user': request.user,
        'data': data,
        'all_templates': all_templates
    }

    return render(request, template, context)


@login_required
def get_relationtemplate(request, template_id):
    """
    Returns data on fillable fields in a :class:`.RelationTemplate`\.

    This view will return JSON if ``format=json`` is passed in the GET request.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    template_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    relation_template = get_object_or_404(RelationTemplate, pk=template_id)

    data = {
        'fields': relations.get_fields(relation_template),
        'name': relation_template.name,
        'description': relation_template.description,
        'id': template_id,
        'expression': relation_template.expression,
    }
    response_format = request.GET.get('format', None)
    if response_format == 'json':
        return JsonResponse(data)

    template = "annotations/relationtemplate_show.html"
    context = {
        'user': request.user,
        'data': data,
    }

    return render(request, template, context)


@login_required
def create_from_relationtemplate(request, template_id):
    """
    Create a :class:`.RelationSet` and constituent :class:`.Relation`\s from
    a :class:`.RelationTemplate` and user annotations.

    This is mainly used by the RelationTemplateController in the text
    annotation  view.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    template_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    # TODO: this could also use quite a bit of attention in terms of
    #  modularization.
    print("CREATING HARDCORE")
    template = get_object_or_404(RelationTemplate, pk=template_id)
    if request.method == 'POST':
        data = json.loads(request.body)
        print(data)
        text = get_object_or_404(Text, pk=data['occursIn'])
        project_id = data.get('project')
        if project_id is None:
            project_id = VogonUserDefaultProject.objects.get(for_user=request.user).project.id
        relationset = relations.create_relationset(template, data, request.user, text, project_id)
        response_data = {'relationset': relationset.id}
    else:   # Not sure if we want to do anything for GET requests at this point.
        response_data = {}

    return JsonResponse(response_data)

@login_required
def update_from_relationtemplate(request, template_id):
    """
    Create a :class:`.RelationSet` and constituent :class:`.Relation`\s from
    a :class:`.RelationTemplate` and user annotations.

    This is mainly used by the RelationTemplateController in the text
    annotation  view.

    Parameters
    ----------
    request : `django.http.requests.HttpRequest`
    template_id : int

    Returns
    ----------
    :class:`django.http.response.HttpResponse`
    """

    # TODO: this could also use quite a bit of attention in terms of
    #  modularization.
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    print("UPDATING HARDCORE")
    template = get_object_or_404(RelationTemplate, pk=template_id)
    if request.method == 'PATCH':
        data = json.loads(request.body)
        pp.pprint(data)
        #pdb.set_trace()
        text = get_object_or_404(Text, pk=data['occursIn'])
        project_id = data.get('project')
        if project_id is None:
            project_id = VogonUserDefaultProject.objects.get(for_user=request.user).project.id
        relationset =  relations.update_relationset(template, data, request.user, text, project_id)  #relations.create_relationset(template, data, request.user, text, project_id)
        # for d in data['fields']:
        #     pp.pprint(d.get('part_of'))
    #     response_data = {'relationset': relationset.id}
    # else:   # Not sure if we want to do anything for GET requests at this point.
    #     response_data = {}

    return JsonResponse({"help":"wanted"})

@staff_member_required
def delete_relationtemplate(request, template_id):
    if request.method == 'POST':

        # Check if there is relation template is associated with a relation set before deleting it
        if not RelationSet.objects.filter(template_id=template_id):
            try:
                with transaction.atomic():
                    RelationTemplate.objects.filter(id=template_id).delete()
                    RelationTemplatePart.objects.filter(part_of=template_id).delete()
            except DatabaseError:
                messages.error(request,
                               'ERROR: There was an error while deleting the relation template. Please redo the operation.')
        else:
            messages.error(request,
                           'ERROR: Could not delete relation template because there is data associated with it')

    return HttpResponseRedirect(reverse('list_relationtemplate'))

@login_required
def prepare_edit_relationtemplate(request, relation_id, template_id):

    response_data = {}
    relations = Relation.objects.filter(part_of_id=relation_id)
    relation_template_parts = RelationTemplatePart.objects.filter(part_of_id=template_id).order_by('internal_id')
    for part in relation_template_parts:
        print(part.id)
    '''
    sort out which parts are needed for template parts and add labels
    '''

    temp = {}
    for part in relation_template_parts:
        temp[part.internal_id] = []
        if part.source_label:
            name = "source"
            temp[part.internal_id].append({name: part.source_label})
        if part.object_label:
            name = "object" 
            temp[part.internal_id].append({name: part.object_label})
        if part.predicate_label:
            name = "predicate"
            temp[part.internal_id].append({name: part.predicate_label})
    '''
    collect ids to check for order
    '''
    ids = []
    for relation in relations:
        ids.append(relation.id)
    '''
    ids are added to the order list as they found to show the order of the relations
    '''
    order = []
    for relation in relations:
        if relation.predicate_id in ids:
            order.append(relation.predicate_id)
        if relation.object_object_id in ids:
            order.append(relation.object_object_id)
        if relation.source_object_id in ids:
            order.append(relation.source_object_id)
    '''
    create sets to check for difference and add difference to the order list.
    This adds the last relation to the order list
    '''
    orderSet = set(order)
    idsSet = set(ids)
    diff = list(idsSet.difference(orderSet))
    order.extend(diff)
    '''
    get appellations and concepts for given relations that are need for the template part.
    Must check that object id's are not in ids otherwise an object not found will be thrown.
    Must reverse order since in the loop below the last items will actual be the first due to
    the first getting added to the list first.
    '''
    reverse_order = order[::-1]
    for c, relationId in enumerate(reverse_order):
        relation = Relation.objects.get(id=relationId)
        response_data["relation_id"] = relation.id
        response_data["created"] = relation.created
        response_data["relationSet_id"] = relation.part_of_id
        print("temp is {} and {}".format(temp, c))
        for tempPart in temp[c]:
            if 'source' in tempPart and relation.source_object_id not in ids:
                response_data[tempPart['source']] = {}
                #Get Objects
                source_appellation = Appellation.objects.get(id=relation.source_object_id)
                source_concept = Concept.objects.get(id=source_appellation.interpretation_id)
                #Serializers
                serial = AppellationSerializer(source_appellation, context={'request': request})
                response_data[tempPart['source']]['appellation'] = serial.data
                serial = ConceptSerializer(source_concept, context={'request': request})
                response_data[tempPart['source']]['concept'] = serial.data
                # Must include part of id
                #response_data[tempPart['source']]['part_of'] = relation.part_of_id
            elif 'object' in tempPart and relation.object_object_id not in ids:
                response_data[tempPart['object']] = {}
                #Get Objects
                object_appellation = Appellation.objects.get(id=relation.object_object_id)
                object_concept = Concept.objects.get(id=object_appellation.interpretation_id)
                #Serializers
                serial = AppellationSerializer(object_appellation, context={'request': request})
                response_data[tempPart['object']]['appellation'] = serial.data
                serial = ConceptSerializer(object_concept, context={'request': request})
                response_data[tempPart['object']]['concept'] = serial.data
                # Must include part of id
                #response_data[tempPart['object']]['part_of'] = relation.part_of_id
            elif 'predicate' in tempPart and relation.predicate_id not in ids:
                response_data[tempPart['predicate']] = {}
                #Get Objects
                predicate_appellation = Appellation.objects.get(id=relation.predicate_id)
                predicate_concept = Concept.objects.get(id=predicate_appellation.interpretation_id)
                #Serializers
                serial = AppellationSerializer(predicate_appellation, context={'request': request})
                response_data[tempPart['predicate']]['appellation'] = serial.data
                serial = ConceptSerializer(predicate_concept, context={'request': request})
                response_data[tempPart['predicate']]['concept'] = serial.data
                # Must include part of id
                #response_data[tempPart['object']]['part_of'] = relation.part_of_id
        else:
            continue

    return JsonResponse(response_data)
