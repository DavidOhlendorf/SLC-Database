from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse


class LoginPageViewTest(TestCase):
    """Tests for the loginpage view."""

    def setUp(self):
        """Set up test client and test user."""
        self.client = Client()
        self.login_url = reverse('login')
        self.search_url = reverse('search:search')
        
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_loginpage_get_anonymous(self):
        """Test GET request to login page for anonymous user."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_loginpage_get_authenticated_redirects(self):
        """Test GET request to login page for authenticated user redirects."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(self.login_url)
        self.assertRedirects(response, self.search_url)

    def test_loginpage_post_valid_credentials(self):
        """Test POST request with valid credentials."""
        response = self.client.post(self.login_url, {
            'user': 'testuser',
            'password': 'testpass123'
        })
        self.assertRedirects(response, self.search_url)

    def test_loginpage_post_invalid_credentials(self):
        """Test POST request with invalid credentials."""
        response = self.client.post(self.login_url, {
            'user': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_loginpage_post_with_next_parameter(self):
        """Test POST request with next parameter redirects correctly."""
        next_url = '/questions/'
        response = self.client.post(self.login_url, {
            'user': 'testuser',
            'password': 'testpass123',
            'next': next_url
        })
        self.assertRedirects(response, next_url, fetch_redirect_response=False)


class LogoutViewTest(TestCase):
    """Tests for the logout_view."""

    def setUp(self):
        """Set up test client and test user."""
        self.client = Client()
        self.logout_url = reverse('accounts:logout')
        self.login_url = reverse('login')
        
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_logout_view(self):
        """Test logout view logs out user and redirects."""
        # First login
        self.client.login(username='testuser', password='testpass123')
        
        # Then logout
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, self.login_url)
        
        # Verify user is logged out
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
