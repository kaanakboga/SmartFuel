from django.shortcuts import render, redirect
from .models import Ship, VoyageLeg, Fuel


def index(request):
    return render(request, "index.html")


def login(request):
    return render(request, "login.html")


def forgotpassword(request):
    return render(request, "forgot-password.html")


def register(request):
    return render(request, "register.html")


def tables(request):
    ships = Ship.objects.all()
    return render(request, "tables.html", {"ships": ships})


def cards(request):
    return render(request, "cards.html")


def charts(request):
    return render(request, "charts.html")


def buttons(request):
    return render(request, "buttons.html")


def blank(request):
    return render(request, "blank.html")


def error(request):
    return render(request, "404.html")


def utilities_animation(request):
    return render(request, "utilities-animation.html")


def utilities_border(request):
    return render(request, "utilities-border.html")


def utilities_color(request):
    return render(request, "utilities-color.html")


def utilities_other(request):
    return render(request, "utilities-other.html")


def fleet_list(request):
    ships = Ship.objects.all()
    return render(request, "tables.html", {"ships": ships})


def add_ship(request):
    if request.method == "POST":
        Ship.objects.create(
            name=request.POST.get("name"),
            ship_type=request.POST.get("ship_type"),
            gt=request.POST.get("gt"),
            fuel_type=request.POST.get("fuel_type"),
            emission_level=request.POST.get("emission_level"),
            compliance_strategy=request.POST.get("compliance_strategy"),
        )
        return redirect("fleet_list")
    return redirect("fleet_list")


def voyage_legs_table(request):
    legs = VoyageLeg.objects.select_related("departure_port", "arrival_port").order_by("-departure_dt")
    return render(request, "voyage_legs.html", {"legs": legs})


def voyage_legs_report_table(request):
    legs = (
        VoyageLeg.objects.select_related("departure_port", "arrival_port")
        .prefetch_related("fuel_items__fuel")
        .order_by("-departure_dt")
    )
    return render(request, "voyage_legs_report.html", {"legs": legs})


def fuels_reference_table(request):
    fuels = Fuel.objects.all().order_by("fuel_group", "fuel_type")
    return render(request, "fuels_reference.html", {"fuels": fuels})