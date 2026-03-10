from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.index, name="index"),

    path("login/", views.login, name="login"),
    path("register/", views.register, name="register"),
    path("forgotpassword/", views.forgotpassword, name="forgot_password"),

    path("cards/", views.cards, name="cards"),
    path("charts/", views.charts, name="charts"),
    path("tables/", views.tables, name="tables"),
    path("error/", views.error, name="error"),
    path("blank/", views.blank, name="blank"),
    path("buttons/", views.buttons, name="buttons"),

    path("utilities-color/", views.utilities_color, name="utilities-color"),
    path("utilities-other/", views.utilities_other, name="utilities-other"),
    path("utilities-border/", views.utilities_border, name="utilities-border"),
    path("utilities-animation/", views.utilities_animation, name="utilities-animation"),

    path("fleet/", views.fleet_list, name="fleet_list"),
    path("add-ship/", views.add_ship, name="add_ship"),

    path("voyage-legs/", views.voyage_legs_table, name="voyage_legs"),
    path("voyage-legs-report/", views.voyage_legs_report_table, name="voyage_legs_report"),

    # NEW: fuel reference table page
    path("fuels-reference/", views.fuels_reference_table, name="fuels_reference"),
]