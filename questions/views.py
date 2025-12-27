# questions/views.py
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.http import Http404, JsonResponse

from django.views import View
from django.views.generic import DetailView, UpdateView
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator


from accounts.mixins import EditorRequiredMixin

from django.db.models import Prefetch
from django.db import transaction

from .models import Question, Keyword
from variables.models import Variable
from waves.models import Wave, WaveQuestion
from pages.models import WavePage, WavePageQuestion 

from .forms import QuestionEditForm



# View für Detailanzeige einer Frage
class QuestionDetail(DetailView):
    model = Question
    template_name = "questions/detail.html"
    context_object_name = "question"

    def get_queryset(self):
        return (
            Question.objects
            .select_related("construct")  
            .prefetch_related(
                Prefetch(
                    "waves",
                    queryset=Wave.objects.order_by("-id"),
                )
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        question = self.object

        waves = list(question.waves.all())
        wave_param = self.request.GET.get("wave")

        active_wave = None
        if waves:
            if wave_param and any(str(w.id) == wave_param for w in waves):
                active_wave = next(w for w in waves if str(w.id) == wave_param)
            else:
                active_wave = waves[0]

        if active_wave:
            # Variablen in aktiver Welle
            variables = (
                Variable.objects
                .filter(question=question, waves=active_wave)
                .only("id", "varname", "varlab")
                .order_by("varname")
            )

            # Seite der aktiven Welle
            page = (
                WavePage.objects
                .filter(
                    page_questions__question=question,
                    waves=active_wave,
                )
                .only("id", "pagename")
                .first()
            )
        else:
            variables = Variable.objects.none()
            page = None

        if page:
            screenshots = list(page.screenshots.all())
        else:
            screenshots = []
 

        ctx.update({
            "waves": waves,
            "active_wave": active_wave,
            "variables": variables,
            "page": page, 
            "screenshots": screenshots,
        })
        return ctx
    
# View zum Anlegen einer neuen Frage 
class QuestionCreateFromPageView(EditorRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, page_id, *args, **kwargs):
        page = get_object_or_404(WavePage, pk=page_id)

        # Harte Sperre: wenn Seite an locked-wave hängt → kein Neuanlegen
        if page.waves.filter(is_locked=True).exists():
            messages.error(
                request,
                "Auf dieser Seite können keine neuen Fragen angelegt werden, "
                "weil sie mit einer abgeschlossenen Befragung verknüpft ist."
            )
            url = reverse("pages:page_detail", kwargs={"pk": page.pk})
            wave = request.GET.get("wave")
            if wave:
                url = f"{url}?wave={wave}"
            return redirect(url)

        # Erlaubte Waves: nur Waves der Seite, die NICHT locked sind
        allowed_waves_qs = page.waves.filter(is_locked=False)

        # vom Modal: waves=<id>&waves=<id>...
        selected_ids = request.POST.getlist("waves")
        # defensive: nur IDs zulassen, die in allowed_waves liegen
        selected_waves = list(allowed_waves_qs.filter(id__in=selected_ids))

        if not selected_waves:
            messages.error(request, "Bitte wähle mindestens eine Befragungsgruppe aus.")
            url = reverse("pages:page_detail", kwargs={"pk": page.pk})
            wave = request.GET.get("wave")
            if wave:
                url = f"{url}?wave={wave}"
            return redirect(url)

        with transaction.atomic():
            q = Question.objects.create(questiontext="")

            WavePageQuestion.objects.create(
                wave_page=page,
                question=q,
            )

            for w in selected_waves:
                WaveQuestion.objects.get_or_create(wave=w, question=q)

        # Redirect auf Edit-View
        base = reverse("questions:question_edit", kwargs={"pk": q.pk})

        # page ist Pflicht für die Edit-View
        params = f"page={page.pk}"

        # optional: aktive wave für UI mitgeben
        wave = request.GET.get("wave")
        if wave and any(str(w.id) == str(wave) for w in selected_waves):
            params += f"&wave={wave}"
        else:
            params += f"&wave={selected_waves[0].id}"

        return redirect(f"{base}?{params}")
    

# View zum Bearbeiten einer Frage    
class QuestionUpdateView(EditorRequiredMixin, UpdateView):
    model = Question
    form_class = QuestionEditForm
    template_name = "questions/question_form.html"
    context_object_name = "question"

    # ---- helpers -------------------------------------------------
    def _get_page_from_request(self, question: Question) -> WavePage:
        """
        Edit-View ist IMMER seitenkontextbasiert.
        page kommt als GET-Parameter (?page=<id>) und muss zur Frage passen.
        """
        page_id = self.request.GET.get("page")
        if not page_id:
            raise Http404("Fehlender Seitenkontext (page).")

        page = get_object_or_404(WavePage, pk=page_id)

        if not WavePageQuestion.objects.filter(wave_page=page, question=question).exists():
            raise Http404("Diese Frage ist nicht mit der angegebenen Seite verknüpft.")

        return page

    def _preserve_querystring(self, base_url: str) -> str:
        """
        Hängt page/wave an URLs an, falls vorhanden.
        """
        page = self.request.GET.get("page")
        wave = self.request.GET.get("wave")

        params = []
        if page:
            params.append(f"page={page}")
        if wave:
            params.append(f"wave={wave}")

        if not params:
            return base_url
        return base_url + "?" + "&".join(params)


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        question = self.get_object()
        page = self._get_page_from_request(question)

        ctx["page"] = page
        ctx["active_wave_id"] = self.request.GET.get("wave")

        return ctx

    def form_valid(self, form):
        _ = self._get_page_from_request(self.get_object())
        messages.success(self.request, "Frage gespeichert.")
        return super().form_valid(form)
    

    def get_success_url(self):
        url = reverse("questions:question_edit", kwargs={"pk": self.object.pk})
        return self._preserve_querystring(url)

    def get(self, request, *args, **kwargs):
        # Wenn page fehlt, lieber sauberer Hinweis als stilles Fehlverhalten
        if not request.GET.get("page"):
            messages.error(request, "Fehlender Seitenkontext. Bitte öffne die Frage aus einer Seite heraus.")
            # falls es eine Question-Detail-Seite gibt:
            try:
                return redirect(reverse("questions:question_detail", kwargs={"pk": kwargs["pk"]}))
            except Exception:
                raise Http404("Fehlender Seitenkontext (page).")
        return super().get(request, *args, **kwargs)
    


# Views für Keyword-Suche und -Anlage
class KeywordSearchView(EditorRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()

        if len(q) < 2:
            return JsonResponse([], safe=False)

        qs = (
            Keyword.objects
            .filter(name__icontains=q)
            .order_by("name")[:15]
        )

        data = [{"value": kw.id, "text": kw.name} for kw in qs]
        return JsonResponse(data, safe=False)


# View zum Anlegen eines neuen Keywords
class KeywordCreateView(EditorRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        name = (request.POST.get("name") or "").strip()

        if len(name) < 2:
            return JsonResponse({"error": "Keyword zu kurz."}, status=400)

        # case-insensitive
        existing = Keyword.objects.filter(name__iexact=name).first()
        if existing:
            return JsonResponse({"value": existing.id, "text": existing.name})

        kw = Keyword.objects.create(name=name)
        return JsonResponse({"value": kw.id, "text": kw.name})