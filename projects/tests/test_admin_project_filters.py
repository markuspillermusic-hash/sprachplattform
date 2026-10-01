from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from projects.models import Project


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminProjectFilterTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_user(
            username="admin-filters", is_staff=True, must_change_password=False,
            demo_projects_initialized=True,
        )
        self.teacher = users.objects.create_user(
            username="teacher-filters", must_change_password=False,
            demo_projects_initialized=True,
        )
        self.own = Project.objects.create(owner=self.admin, title="Mein Hörtext")
        self.own_demo = Project.objects.create(owner=self.admin, title="Meine Demo", demo_key="station-de")
        self.other = Project.objects.create(owner=self.teacher, title="Fremder Hörtext")
        self.other_demo = Project.objects.create(owner=self.teacher, title="Fremde Demo", demo_key="station-de")
        self.client.force_login(self.admin)
        self.url = reverse("projects:list")

    def assert_projects(self, params, expected):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(response.context["projects"].values_list("pk", flat=True)),
                            {project.pk for project in expected})
        self.assertEqual(response.context["project_count"], len(expected))
        return response

    def test_admin_defaults_to_own_projects_without_demos_and_has_visible_studio_link(self):
        response = self.assert_projects({}, [self.own])
        self.assertContains(response, 'aria-label="Hörtexte filtern"')
        self.assertContains(response, reverse("audio_studio:editor", args=[self.own.pk]))
        self.assertNotContains(response, self.other.title)
        self.assertNotContains(response, self.other_demo.title)

    def test_all_users_can_be_shown_with_or_without_demos(self):
        self.assert_projects({"owner": "all"}, [self.own, self.other])
        self.assert_projects({"owner": "all", "content": "all"},
                             [self.own, self.other, self.own_demo, self.other_demo])
        self.assert_projects({"owner": "all", "content": "demo"}, [self.own_demo, self.other_demo])

    def test_specific_owner_and_demo_filters_combine(self):
        response = self.assert_projects({"owner": str(self.teacher.pk), "content": "all"},
                                        [self.other, self.other_demo])
        self.assertContains(response, f'value="{self.teacher.pk}" selected')
        self.assert_projects({"owner": str(self.teacher.pk), "content": "demo"}, [self.other_demo])

    def test_other_users_filter_excludes_own_projects(self):
        self.assert_projects({"owner": "other", "content": "all"}, [self.other, self.other_demo])
        self.assert_projects({"owner": "mine", "content": "demo"}, [self.own_demo])

    def test_invalid_filters_fall_back_to_own_projects_without_demos(self):
        response = self.assert_projects({"owner": "invalid", "content": "invalid"}, [self.own])
        self.assertEqual(response.context["owner_filter"], "mine")
        self.assertEqual(response.context["content_filter"], "text")
        self.assert_projects({"owner": "999999999"}, [self.own])

    def test_normal_user_cannot_expand_visibility_using_admin_query_parameters(self):
        self.client.force_login(self.teacher)
        for params in ({"owner": "all"}, {"owner": str(self.admin.pk)}, {"owner": "other", "content": "demo"}):
            response = self.assert_projects(params, [self.other, self.other_demo])
            self.assertFalse(response.context["admin_view"])
            self.assertNotContains(response, 'aria-label="Hörtexte filtern"')
            self.assertNotContains(response, self.own.title)
            self.assertNotContains(response, self.admin.username)

    def test_admin_role_without_staff_flag_also_has_filters(self):
        self.admin.is_staff = False
        self.admin.role = self.admin.Role.ADMIN
        self.admin.save(update_fields=["is_staff", "role"])
        response = self.assert_projects({"owner": "all"}, [self.own, self.other])
        self.assertTrue(response.context["admin_view"])
