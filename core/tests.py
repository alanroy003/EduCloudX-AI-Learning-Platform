# core/tests.py

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import Discipline, Course

User = get_user_model()

class SmokeTests(TestCase):
    def setUp(self):
        # Test client
        self.client = Client()

        # 1. Create a test user
        self.username = "testuser"
        self.password = "testpass123"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password
        )

        # 2. Create a Discipline instance
        self.discipline = Discipline.objects.create(
            name="Test Discipline",
            slug="test-discipline"
        )

        # 3. Create a Course instance and assign the discipline
        self.course = Course.objects.create(
            code="TST101",
            title="Test Course",
            slug="test-course",
            description="Test description",
            discipline=self.discipline
        )

    def test_register_and_login(self):
        # Register page should return GET 200
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)

        # Can we log in with the existing user?
        login_ok = self.client.login(
            username=self.username,
            password=self.password
        )
        self.assertTrue(login_ok)

    def test_post_crud_flow(self):
        # First, log in
        self.client.login(username=self.username, password=self.password)

        # 1) GET request to the new post form
        url_create = reverse("create_post", kwargs={"slug": self.course.slug})
        response_get = self.client.get(url_create)
        self.assertEqual(response_get.status_code, 200)

        # 2) Create a post via POST
        response_post = self.client.post(url_create, {
            "title": "Test Title",
            "content": "Test content"
        })
        # We expect a redirect (302) on success
        self.assertEqual(response_post.status_code, 302)

        # 3) Was it actually saved to the DB?
        # It comes via user.posts because related_name='posts' is used
        post = self.user.posts.get(title="Test Title")

        # 4) Correct redirection to the detail page
        detail_url = reverse("post_detail", kwargs={"slug": post.slug})
        self.assertRedirects(response_post, detail_url)
