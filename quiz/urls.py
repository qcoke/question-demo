from django.urls import path

from .views import start_test, test_question, test_result

urlpatterns = [
    path("", start_test, name="start_test"),
    path("attempt/<int:attempt_id>/question/<int:order>/", test_question, name="test_question"),
    path("attempt/<int:attempt_id>/result/", test_result, name="test_result"),
]
