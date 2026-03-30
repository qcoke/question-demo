from django.urls import path

from .views import start_test, submit_test

urlpatterns = [
    path("", start_test, name="start_test"),
    path("submit/", submit_test, name="submit_test"),
]
