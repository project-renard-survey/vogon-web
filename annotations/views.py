from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, JsonResponse
from django.template import RequestContext, loader
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.files import File
from django.core.serializers import serialize

from django.contrib.auth import login,authenticate
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required

from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.views.generic.edit import FormView

from django.conf import settings

from django.db.models import Q
from django.utils.safestring import mark_safe

from django.forms import formset_factory

from rest_framework import status
from rest_framework.response import Response
from rest_framework.settings import api_settings

from rest_framework import viewsets, exceptions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route
from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination

from guardian.shortcuts import get_objects_for_user

from concepts.models import Concept
from concepts.authorities import search
from concepts.tasks import search_concept

from models import *
from forms import *
from serializers import *
from tasks import *

import hashlib
from itertools import chain
from collections import OrderedDict
import requests
import re
from urlnorm import norm
from itertools import chain
import uuid
import igraph
import copy

import json

from django.shortcuts import render


def home(request):
    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse('dashboard'))
    return HttpResponseRedirect(reverse('django.contrib.auth.views.login'))


def user_texts(user):
    return Text.objects.filter(relation__createdBy__pk=user.id).distinct()


def basepath(request):
    """
    Generate the base path (domain + path) for the site.
    """
    if request.is_secure():
        scheme = 'https://'
    else:
        scheme = 'http://'
    return scheme + request.get_host() + settings.SUBPATH

@csrf_protect
def register(request):
    """
    Provide registration view and stores a user on receiving user detail from registration form.
    Parameters
    ----------
    request : HTTPRequest
        The request after submitting registration form.
    Returns
    ----------
    :template:
        Renders registration form for get request. Redirects to dashboard
        for post request.
    """
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = VogonUser.objects.create_user(
            form.cleaned_data['username'],
            form.cleaned_data['email'],
            password=form.cleaned_data['password1'],
            )

            g = Group.objects.get_or_create(name='Public')[0]
            user.groups.add(g)
            user.save()
            new_user = authenticate(username=form.cleaned_data['username'],
                                    password=form.cleaned_data['password1'])
            # Logs in new user
            login(request, new_user)
            return HttpResponseRedirect(reverse('dashboard'))
    else:
        form = RegistrationForm()
    variables = RequestContext(request, {
    'form': form
    })

    return render(request,
    'registration/register.html',
    {'form': form},
    )

def user_recent_texts(user):
    by_relations = Text.objects.filter(relation__createdBy__pk=user.id)
    by_appellations = Text.objects.filter(appellation__createdBy__pk=user.id)
    result_list = list(set(chain(by_relations, by_appellations)))
    return result_list


def json_response(func):
    def decorator(request, *args, **kwargs):
        objects = func(request, *args, **kwargs)

        try:
            data = json.dumps(objects)
        except:
            if not hasattr(objects, '__iter__'):
                data = serialize("json", [objects])[1:-1]
            else:
                data = serialize("json", objects)
        return HttpResponse(data, "application/json")
    return decorator


@login_required
def user_settings(request):
    """ User profile settings"""

    if request.method == 'POST':
        form = UserChangeForm(request.POST)
        if form.is_valid():
            for field in ['first_name', 'last_name', 'email']:
                value = request.POST.get(field, None)
                if value:
                    setattr(request.user, field, value)
            request.user.save()
            return HttpResponseRedirect('/accounts/profile/')
    else:
        form = UserChangeForm(instance=request.user)

    template = loader.get_template('annotations/settings.html')
    context = RequestContext(request, {
        'user': request.user,
        'form': form,
        'subpath': settings.SUBPATH,
    })
    return HttpResponse(template.render(context))


@login_required
def dashboard(request):
    """
    Provides the user's personalized dashboard.
    """
    template = loader.get_template('annotations/dashboard.html')
    texts = user_recent_texts(request.user)
    context = RequestContext(request, {
        'user': request.user,
        'subpath': settings.SUBPATH,
        'baselocation': basepath(request),
        'texts': texts,
        'textCount': len(texts),
        'appellationCount': Appellation.objects.filter(createdBy__pk=request.user.id).filter(asPredicate=False).distinct().count(),
        'relationCount': Relation.objects.filter(createdBy__pk=request.user.id).distinct().count(),
    })
    return HttpResponse(template.render(context))


def network(request):
    """
    Provides a network browser view.
    """
    template = loader.get_template('annotations/network.html')
    context = {
        'baselocation': basepath(request),
        'user': request.user,
    }
    return HttpResponse(template.render(context))


@login_required
def list_texts(request):
    """
    List all of the texts that the user can see, with links to annotate them.
    """
    template = loader.get_template('annotations/list_texts.html')

    text_list = get_objects_for_user(request.user, 'annotations.view_text')

    # text_list = Text.objects.all()
    paginator = Paginator(text_list, 25)

    page = request.GET.get('page')
    try:
        texts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        texts = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        texts = paginator.page(paginator.num_pages)

    context = {
        'texts': texts,
        'user': request.user,
    }
    return HttpResponse(template.render(context))


@login_required
def collection_texts(request, collectionid):
    """
    List all of the texts that the user can see, with links to annotate them.
    """
    template = loader.get_template('annotations/collection_texts.html')

    text_list = get_objects_for_user(request.user, 'annotations.view_text')
    text_list = text_list.filter(partOf=collectionid)

    # text_list = Text.objects.all()
    paginator = Paginator(text_list, 25)

    page = request.GET.get('page')
    try:
        texts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        texts = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        texts = paginator.page(paginator.num_pages)

    context = {
        'texts': texts,
        'user': request.user,
        'collection': TextCollection.objects.get(pk=collectionid)
    }
    return HttpResponse(template.render(context))


@ensure_csrf_cookie
@login_required
def text(request, textid):
    """
    Provides the main text annotation view.
    """
    template = loader.get_template('annotations/text.html')
    text = get_object_or_404(Text, pk=textid)

    # If a text is restricted, then the user needs explicit permission to
    #  access it.
    if not text.public and not request.user.has_perm('annotations.view_text'):
        # TODO: return a pretty templated response.
        return HttpResponseForbidden("Sorry, this text is restricted.")

    context = RequestContext(request, {
        'textid': textid,
        'text': text,
        'userid': request.user.id,
        'title': 'Annotate Text',
        'baselocation': basepath(request),
    })
    return HttpResponse(template.render(context))


### REST API class-based views.


class UserViewSet(viewsets.ModelViewSet):
    queryset = VogonUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )


class RepositoryViewSet(viewsets.ModelViewSet):
    queryset = Repository.objects.all()
    serializer_class = RepositorySerializer
    permission_classes = (IsAuthenticated, )


class RemoteCollectionViewSet(viewsets.ViewSet):
    def list(self, request, repository_pk=None):
        repository = Repository.objects.get(pk=repository_pk)
        manager = get_manager(repository.manager)(repository.endpoint)
        return Response(manager.collections())

    def retrieve(self, request, pk=None, repository_pk=None):
        repository = Repository.objects.get(pk=repository_pk)
        manager = get_manager(repository.manager)(repository.endpoint)
        return Response(manager.collection(pk))


class RemoteResourceViewSet(viewsets.ViewSet):
    def list(self, request, collection_pk=None, repository_pk=None):
        repository = Repository.objects.get(pk=repository_pk)
        manager = get_manager(repository.manager)(repository.endpoint)
        return Response(manager.collection(collection_pk))

    def retrieve(self, request, pk=None, collection_pk=None, repository_pk=None):
        repository = Repository.objects.get(pk=repository_pk)
        manager = get_manager(repository.manager)(repository.endpoint)
        return Response(manager.resource(pk))


class AnnotationFilterMixin(object):
    """
    Mixin for :class:`viewsets.ModelViewSet` that provides filtering by
    :class:`.Text` and :class:`.User`\.
    """
    def get_queryset(self, *args, **kwargs):
        queryset = super(AnnotationFilterMixin, self).get_queryset(*args, **kwargs)

        textid = self.request.query_params.get('text', None)
        userid = self.request.query_params.get('user', None)
        if textid:
            queryset = queryset.filter(occursIn=int(textid))
        if userid:
            queryset = queryset.filter(createdBy__pk=userid)
        elif userid is not None:
            queryset = queryset.filter(createdBy__pk=self.request.user.id)
        return queryset


class AppellationViewSet(AnnotationFilterMixin, viewsets.ModelViewSet):
    queryset = Appellation.objects.filter(asPredicate=False)
    serializer_class = AppellationSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )

    def create(self, request, *args, **kwargs):
        data = request.data

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset(self, *args, **kwargs):
        queryset = super(AppellationViewSet, self).get_queryset(*args, **kwargs)

        concept = self.request.query_params.get('concept', None)
        text = self.request.query_params.get('text', None)
        thisuser = self.request.query_params.get('thisuser', False)
        if thisuser:
            queryset = queryset.filter(createdBy_id=self.request.user.id)
        if concept:
            queryset = queryset.filter(interpretation_id=concept)
        if text:
            queryset = queryset.filter(occursIn_id=text)
        return queryset


class PredicateViewSet(AnnotationFilterMixin, viewsets.ModelViewSet):
    queryset = Appellation.objects.filter(asPredicate=True)
    serializer_class = AppellationSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )


class RelationViewSet(viewsets.ModelViewSet):
    queryset = Relation.objects.all()
    serializer_class = RelationSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )

    def get_queryset(self, *args, **kwargs):
        """
        Supports filtering by :class:`.Text`\, :class:`.User`\, node concept
        type, and predicate concept type.
        """

        queryset = super(RelationViewSet, self).get_queryset(*args, **kwargs)

        textid = self.request.query_params.getlist('text')
        userid = self.request.query_params.getlist('user')
        typeid = self.request.query_params.getlist('type')
        conceptid = self.request.query_params.getlist('concept')
        related_concepts = self.request.query_params.getlist('related_concepts')

        # Refers to the predicate's interpretation, not the predicate itself.
        predicate_conceptid = self.request.query_params.getlist('predicate')

        # TODO: clean this up.
        if len(textid) > 0:
            queryset = queryset.filter(occursIn__in=[int(t) for t in textid])
        if len(typeid) > 0:
            queryset = queryset.filter(source__interpretation__typed__pk__in=[int(t) for t in typeid]).filter(object__interpretation__typed__pk__in=[int(t) for t in typeid])
        if len(predicate_conceptid) > 0:
            queryset = queryset.filter(predicate__interpretation__pk__in=[int(t) for t in predicate_conceptid])
        if len(conceptid) > 0:  # Source or target concept in `concept`.
            queryset = queryset.filter(Q(source__interpretation__id__in=[int(c) for c in conceptid]) | Q(object__interpretation__id__in=[int(c) for c in conceptid]))
        if len(related_concepts) > 0:  # Source or target concept in `concept`.
            queryset = queryset.filter(Q(source__interpretation__id__in=[int(c) for c in related_concepts]) & Q(object__interpretation__id__in=[int(c) for c in related_concepts]))
            print queryset
        if len(userid) > 0:
            queryset = queryset.filter(createdBy__pk__in=[int(i) for i in userid])
        elif userid is not None and type(userid) is not list:
            queryset = queryset.filter(createdBy__pk=self.request.user.id)

        return queryset


class TemporalBoundsViewSet(viewsets.ModelViewSet, AnnotationFilterMixin):
    queryset = TemporalBounds.objects.all()
    serializer_class = TemporalBoundsSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000


class TextViewSet(viewsets.ModelViewSet):
    queryset = Text.objects.all()
    serializer_class = TextSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )
    # pagination_class = StandardResultsSetPagination

    def get_queryset(self, *args, **kwargs):
        """
        A user can see only their own :class:`.TextCollection`\s.
        """

        queryset = super(TextViewSet, self).get_queryset(*args, **kwargs)

        textcollectionid = self.request.query_params.get('textcollection', None)
        conceptid = self.request.query_params.getlist('concept')
        related_concepts = self.request.query_params.getlist('related_concepts')

        if textcollectionid:
            queryset = queryset.filter(partOf=int(textcollectionid))
        if len(conceptid) > 0:
            queryset = queryset.filter(appellation__interpretation__pk__in=[int(c) for c in conceptid])
        if len(related_concepts) > 1:
            queryset = queryset.filter(appellation__interpretation_id=int(related_concepts[0])).filter(appellation__interpretation_id=int(related_concepts[1]))

        return queryset.distinct()


class TextCollectionViewSet(viewsets.ModelViewSet):
    queryset = TextCollection.objects.all()
    serializer_class = TextCollectionSerializer
    permission_classes = (IsAuthenticated, )

    def get_queryset(self, *args, **kwargs):
        """
        """
        queryset = super(TextCollectionViewSet, self).get_queryset(*args, **kwargs)

        userid = self.request.query_params.get('user', None)
        if userid:
            queryset = queryset.filter(ownedBy__pk=self.userid)
        else:
            queryset = queryset.filter(ownedBy__pk=self.request.user.id)
        return queryset

    def create(self, request, *args, **kwargs):

        data = request.data
        if 'ownedBy' not in data:
            data['ownedBy'] = request.user.id
        if 'participants' not in data:
            data['participants'] = []

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)
        headers = self.get_success_headers(data)

        return Response(serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers)



class TypeViewSet(viewsets.ModelViewSet):
    queryset = Type.objects.all()
    serializer_class = TypeSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )


class ConceptViewSet(viewsets.ModelViewSet):
    queryset = Concept.objects.all()
    serializer_class = ConceptSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, )

    def create(self, request, *args, **kwargs):
        data = request.data
        if data['uri'] == 'generate':
            data['uri'] = 'http://vogonweb.net/{0}'.format(uuid.uuid4())

        if 'lemma' not in data:
            data['lemma'] = data['label'].lower()

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)
        headers = self.get_success_headers(data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    def get_queryset(self, *args, **kwargs):
        """
        Filter by part of speach (``pos``).
        """
        queryset = super(ConceptViewSet, self).get_queryset(*args, **kwargs)

        # Limit results to those with ``pos``.
        pos = self.request.query_params.get('pos', None)
        if pos:
            if pos != 'all':
                queryset = queryset.filter(pos__in=[pos.upper(), pos.lower()])

        # Search Concept labels for ``search`` param.
        query = self.request.query_params.get('search', None)
        remote = self.request.query_params.get('remote', False)
        if query:
            if pos == 'all':
                pos = None

            if remote:  # Spawn asynchronous calls to authority services.
                search_concept.delay(query, pos=pos)
            queryset = queryset.filter(label__icontains=query)

        return queryset

@login_required
def upload_file(request):
    """
    Upload a file and save the text instance.

    Parameters
    ----------
    request : HTTPRequest
        The request after submitting file upload form
    """
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():

            text = handle_file_upload(request, form)
            return HttpResponseRedirect(reverse('text', args=[text.id]))

    else:
        form = UploadFileForm()

    template = loader.get_template('annotations/upload_file.html')
    context = RequestContext(request, {
        'user': request.user,
        'form': form,
        'subpath': settings.SUBPATH,
    })
    return HttpResponse(template.render(context))


def handle_file_upload(request, form):
    """
    Handle the uploaded file and route it to corresponding handlers

    Parameters
    ----------
    request : HTTPRequest
        The request after submitting file upload form
    form : Form
        The form with uploaded content
    """
    uploaded_file = request.FILES['filetoupload']
    text_title = form.cleaned_data['title']
    date_created = form.cleaned_data['datecreated']
    is_public = form.cleaned_data['ispublic']
    user = request.user
    file_content = None
    if uploaded_file.content_type == 'text/plain':
        file_content = extract_text_file(uploaded_file)
    elif uploaded_file.content_type == 'application/pdf':
        file_content = extract_pdf_file(uploaded_file)

    # Save the content if the above extractors extracted something
    if file_content != None:
        tokenized_content = tokenize(file_content)
        return save_text_instance(tokenized_content, text_title, date_created, is_public, user)


def network_data(request):
    project = request.GET.get('project', None)
    user = request.GET.get('user', None)
    text = request.GET.get('text', None)

    queryset = Relation.objects.all()
    if project:
        queryset = queryset.filter(occursIn__partOf_id=project)
    if user:
        queryset = queryset.filter(createdBy_id=user)
    if text:
        queryset = queryset.filter(occursIn_id=text)


    nodes = OrderedDict()
    relations = OrderedDict()
    N = queryset.count()
    max_relation = 0.
    max_node = 0.
    for relation in queryset:
        source = relation.source.interpretation
        target = relation.object.interpretation
        key = tuple(sorted([source.id, target.id]))
        ids = {}
        for node in [source, target]:
            if node.id not in nodes:
                nodes[node.id] = {
                    'id': len(nodes),
                    'concept_id': node.id,
                    'label': node.label,
                    'weight': 1.,
                }
            else:
                nodes[node.id]['weight'] += 1.
            if nodes[node.id]['weight'] > max_node:
                max_node = nodes[node.id]['weight']

        if key in relations:
            relations[key]['weight'] += 1.
        else:
            relations[key] = {
                'source': nodes[source.id],
                'target': nodes[target.id],
                'id': relation.id,
                'weight': 1.,
            }
        if relations[key]['weight'] > max_relation:
            max_relation = relations[key]['weight']

    for key, relation in relations.items():
        relation['size'] = 3. * relation['weight']/max_relation
    for key, node in nodes.items():
        node['size'] = 3. * node['weight']/max_node

    graph = igraph.Graph()
    graph.add_vertices(len(nodes))
    graph.add_edges([(relation['source']['id'], relation['target']['id']) for relation in relations.values()])
    layout = graph.layout_fruchterman_reingold()
    for i, coords in enumerate(layout._coords):
        nodes.values()[i]['x'] = coords[0] * 25
        nodes.values()[i]['y'] = coords[1] * 25


    return JsonResponse({'nodes': nodes.values(), 'edges': relations.values()})


@login_required
def add_text_to_collection(request, *args, **kwargs):
    # TODO: add exception handling.

    # if request.method == 'POST':
    text_id = request.GET.get('text', None)
    collection_id  = request.GET.get('collection', None)
    if text_id and collection_id:
        text = Text.objects.get(pk=text_id)
        collection = TextCollection.objects.get(pk=collection_id)
        collection.texts.add(text)
        collection.save()

    return JsonResponse({})


@login_required
def user_details(request, userid, *args, **kwargs):
    user = get_object_or_404(VogonUser, pk=userid)
    template = loader.get_template('annotations/user_details.html')
    context = RequestContext(request, {
        'user': request.user,
        'detail_user': user,
    })
    return HttpResponse(template.render(context))


def list_collections(request, *args, **kwargs):
    queryset = TextCollection.objects.all()
    paginator = Paginator(queryset, 25)

    page = request.GET.get('page')
    try:
        collections = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        collections = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        collections = paginator.page(paginator.num_pages)

    template = loader.get_template('annotations/list_collections.html')
    context = RequestContext(request, {
        'user': request.user,
        'collections': collections
    })
    return HttpResponse(template.render(context))


def relation_details(request, concept_a_id, concept_b_id):
    concept_a = get_object_or_404(Concept, pk=concept_a_id)
    concept_b = get_object_or_404(Concept, pk=concept_b_id)

    queryset = Relation.objects.filter(
        Q(source__interpretation__id__in=[concept_a_id, concept_b_id]) \
        & Q(object__interpretation__id__in=[concept_a_id, concept_b_id]))


    template = loader.get_template('annotations/relations.html')
    context = RequestContext(request, {
        'user': request.user,
        'relations': queryset,
    })
    return HttpResponse(template.render(context))


def concept_details(request, conceptid):
    concept = get_object_or_404(Concept, pk=conceptid)
    appellations = Appellation.objects.filter(interpretation_id=conceptid)
    texts = set()
    appellations_by_text = OrderedDict()
    for appellation in appellations:
        text = appellation.occursIn
        texts.add(text)
        if text.id not in appellations_by_text:
            appellations_by_text[text.id] = []
        appellations_by_text[text.id].append(appellation)

    template = loader.get_template('annotations/concept_details.html')
    context = RequestContext(request, {
        'user': request.user,
        'concept': concept,
        'appellations': appellations_by_text,
        'texts': texts,
    })

    return HttpResponse(template.render(context))


@staff_member_required
def relation_template(request):
    """
    Staff can use this view to create :class:`.RelationTemplate`\s.
    """

    # Each RelationTemplatePart is a "triple", the subject or object of which
    #  might be another RelationTemplatePart.
    formset = formset_factory(RelationTemplatePartForm)
    form_class = RelationTemplateForm   # e.g. Name, Description.

    context = {}
    error = None    # TODO: <-- make this less hacky.
    if request.POST:
        # Instatiate both form(set)s with data.
        relationtemplatepart_formset = formset(request.POST)
        context['formset'] = relationtemplatepart_formset
        relationtemplate_form = form_class(request.POST)

        if relationtemplatepart_formset.is_valid() and relationtemplate_form.is_valid():
            # We commit the RelationTemplate to the database first, so that we
            #  can use it in the FK relation ``RelationTemplatePart.part_of``.
            relationTemplate = relationtemplate_form.save()

            # We index RTPs so that we can fill FK references among them.
            relationTemplateParts = {}
            dependency_order = {}    # Source RTP index -> target RTP index.
            for form in relationtemplatepart_formset:
                relationTemplatePart = RelationTemplatePart()
                relationTemplatePart.part_of = relationTemplate
                relationTemplatePart.internal_id = form.cleaned_data['internal_id']

                # Since many field names are shared for source, predicate, and
                #  object, this approach should cut down on a lot of repetitive
                #  code.
                for part in ['source', 'predicate', 'object']:
                    setattr(relationTemplatePart, part + '_node_type',
                            form.cleaned_data[part + '_node_type'])
                    setattr(relationTemplatePart, part + '_prompt_text',
                            form.cleaned_data[part + '_prompt_text'])

                    # Node is a concept Type. e.g. ``E20 Person``.
                    if form.cleaned_data[part + '_node_type'] == 'TP':
                        setattr(relationTemplatePart, part + '_type',
                                form.cleaned_data[part + '_type'])
                        setattr(relationTemplatePart, part + '_description',
                                form.cleaned_data[part + '_description'])

                    # Node is a specific Concept, e.g. ``employ``.
                    elif form.cleaned_data[part + '_node_type'] == 'CO':
                        setattr(relationTemplatePart, part + '_concept',
                                form.cleaned_data[part + '_concept'])

                    # Node is another RelationTemplatePart.
                    elif form.cleaned_data[part + '_node_type'] == 'RE':
                        target_id = form.cleaned_data[part + '_relationtemplate_internal_id']
                        setattr(relationTemplatePart,
                                part + '_relationtemplate_internal_id',
                                target_id)
                        if target_id > -1:
                            # This will help us to figure out the order in
                            #  which to save RTPs.
                            dependency_order[relationTemplatePart.internal_id] = target_id

                # Index so that we can fill FK references among RTPs.
                relationTemplateParts[relationTemplatePart.internal_id] = relationTemplatePart

            # If there is interdependency among RTPs, determine and execute
            #  the correct save order.
            if len(dependency_order) > 0:
                # Find the relation template furthest downstream.
                # TODO: is this really better than hitting the database twice?
                start_rtp = copy.deepcopy(dependency_order.keys()[0])
                this_rtp = copy.deepcopy(start_rtp)
                save_order = [this_rtp]
                iteration = 0
                while True:
                    this_rtp = copy.deepcopy(dependency_order[this_rtp])
                    if this_rtp not in save_order:
                        save_order.insert(0, copy.deepcopy(this_rtp))
                    if this_rtp in dependency_order:
                        iteration += 1
                    else:   # Found the downstream relation template.
                        break

                    # Make sure that we're not in an endless loop.
                    # TODO: This is kind of a hacky way to handle the situation.
                    #  Maybe we should move this logic to the validation phase,
                    #  so that we can handle errors in a Django-esque fashion.
                    if iteration > 0 and this_rtp == start_rtp:
                        error = 'Endless loop'
                        break
                if not error:
                    # Resolve internal ids for RTP references into instance pks,
                    #  and populate the RTP _relationtemplate fields.
                    for i in save_order:
                        for part in ['source', 'object']:
                            dep = getattr(relationTemplateParts[i],
                                          part + '_relationtemplate_internal_id')
                            if dep > -1:
                                setattr(relationTemplateParts[i],
                                        part + '_relationtemplate',
                                        relationTemplateParts[dep])
                        if not relationTemplateParts[i].id:
                            relationTemplateParts[i].save()

            # Otherwise, just save the (one and only) RTP.
            elif len(relationTemplateParts) == 1:
                relationTemplateParts.values()[0].save()

            if not error:
                # TODO: when the list view for RTs is implemented, we should
                #  direct the user there.
                return HttpResponseRedirect(reverse('dashboard'))

            else:
                # For now, we can render this view-wide error separately. But
                #  we should probably make this part of the normal validation
                #  process in the future. See comments above.
                context['error'] = error
    else:   # No data, start with a fresh formset.
        context['formset'] = formset()

    return render(request, 'annotations/relationtemplate.html', context)


def list_relationtemplate(request):
    """
    Returns a list of all :class:`.RelationTemplate`\s.
    """
    queryset = RelationTemplate.objects.all()
    data = {
        'templates': [{
            'id': rt.id,
            'name': rt.name,
            'description': rt.description
            } for rt in queryset]
        }
    return JsonResponse(data)


def get_relationtemplate(request, template_id):
    """
    Returns data on fillable fields in a :class:`.RelationTemplate`\.
    """

    template = get_object_or_404(RelationTemplate, pk=template_id)

    fields = []    # The fields that we need the user to fill go in here.
    for tpart in template.template_parts.all():
        for field in ['source', 'predicate', 'object']:
            evidenceRequired = getattr(tpart, '%s_prompt_text' % field)
            nodeType = getattr(tpart, '%s_node_type' % field)
            # The user needs to provide specific concepts for TYPE fields.
            if nodeType == RelationTemplatePart.TYPE:
                fields.append({
                    'type': 'TP',
                    'id': getattr(tpart, '%s_type' % field).id,
                    'label': getattr(tpart, '%s_type' % field).label,
                    'evidence_required': evidenceRequired,
                    'description': getattr(tpart, '%s_description' % field),
                })
            # Even if there is an explicit concept, we may require textual
            #  evidence from the user.
            elif evidenceRequired and nodeType == RelationTemplatePart.CONCEPT:
                fields.append({
                    'type': 'CO',
                    'id': getattr(tpart, '%s_concept' % field).id,
                    'label': getattr(tpart, '%s_concept' % field).label,
                    'evidence_required': evidenceRequired,
                    'description': getattr(tpart, '%s_description' % field),
                })
    data = {
        'fields': fields,
        'name': template.name,
        'description': template.description,
        'id': template_id,
    }
    return JsonResponse(data)
