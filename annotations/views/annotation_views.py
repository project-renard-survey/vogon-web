from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse

from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from annotations.models import Relation, Appellation, VogonUser, Text, RelationSet
from annotations.annotators import annotator_factory

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


@login_required
@ensure_csrf_cookie
def annotate(request, text_id):
    text = get_object_or_404(Text, pk=text_id)
    annotator = annotator_factory(request, text)
    return annotator.render()


@login_required
def annotation_display(request, text_id):
    text = get_object_or_404(Text, pk=text_id)
    annotator = annotator_factory(request, text)
    return annotator.render_display()

@login_required
def annotate_image(request, text_id):
    template = "annotations/annotate_image.html"
    text = Text.objects.get(pk=text_id)

    return render(request, template, context)


def relations(request):
    from annotations.filters import RelationSetFilter

    qs = RelationSet.objects.all()
    filtered = RelationSetFilter(request.GET, queryset=qs)
    qs = filtered.qs
    for r in qs:
        print r.__dict__

    paginator = Paginator(qs, 40)
    page = request.GET.get('page')


    createdBy = request.GET.get('createdBy')
    createdAfter = request.GET.get('createdAfter')
    createdBefore = request.GET.get('createdBefore')
    project = request.GET.get('project')
    terminal_nodes = request.GET.get('terminal_nodes')
    occursIn = request.GET.get('occursIn')

    try:
        relations = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        relations = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        relations = paginator.page(paginator.num_pages)

    context = {
        'paginator': paginator,
        'relations': relations,
        'params': request.GET.urlencode(),
        'filter': filtered,
        'createdBy': createdBy,
        'createdAfter': createdAfter,
        'createdBefore': createdBefore,
        'project': project,
        'terminal_nodes': terminal_nodes,
        'occursIn': occursIn,
    }
    return render(request, 'annotations/relations.html', context)


def relations_graph(request):
    from annotations.filters import RelationSetFilter
    from annotations.views.network_views import generate_network_data_fast
    qs = RelationSet.objects.all()
    filtered = RelationSetFilter(request.GET, queryset=qs)
    qs = filtered.qs

    if request.GET.get('mode', None) == 'data':

        nodes, edges = generate_network_data_fast(qs)
        return JsonResponse({'elements': nodes.values() + edges.values()})

    context = {
        'relations': relations,
        'filter': filtered,
        'data_path': request.path + '?' + request.GET.urlencode() + '&mode=data',
        'params': request.GET.urlencode(),
    }

    return render(request, 'annotations/relations_graph.html', context)
