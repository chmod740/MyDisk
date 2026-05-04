from django.test import TestCase, Client
from django.urls import reverse
from .models import User


class RegistrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('register')

    def test_register_page_loads(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'accounts/register.html')

    def test_register_success(self):
        resp = self.client.post(self.url, {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'testpass123',
            'password2': 'testpass123',
        })
        self.assertRedirects(resp, reverse('file_list'))
        user = User.objects.get(username='newuser')
        self.assertEqual(user.email, 'new@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertEqual(user.storage_quota, 1073741824)  # 1GB default

    def test_register_empty_username(self):
        resp = self.client.post(self.url, {
            'username': '',
            'password': 'testpass123',
            'password2': 'testpass123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='').exists())

    def test_register_password_mismatch(self):
        resp = self.client.post(self.url, {
            'username': 'user1',
            'password': 'testpass123',
            'password2': 'different',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='user1').exists())

    def test_register_short_password(self):
        resp = self.client.post(self.url, {
            'username': 'user1',
            'password': '12345',
            'password2': '12345',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='user1').exists())

    def test_register_duplicate_username(self):
        User.objects.create_user('existing', password='testpass123')
        resp = self.client.post(self.url, {
            'username': 'existing',
            'password': 'testpass123',
            'password2': 'testpass123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(username='existing').count(), 1)

    def test_register_duplicate_email(self):
        User.objects.create_user('user1', email='dup@example.com', password='testpass123')
        resp = self.client.post(self.url, {
            'username': 'user2',
            'email': 'dup@example.com',
            'password': 'testpass123',
            'password2': 'testpass123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(email='dup@example.com').count(), 1)

    def test_register_without_email(self):
        resp = self.client.post(self.url, {
            'username': 'noemail',
            'password': 'testpass123',
            'password2': 'testpass123',
        })
        self.assertRedirects(resp, reverse('file_list'))
        self.assertTrue(User.objects.filter(username='noemail').exists())


class LoginTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.url = reverse('login')

    def test_login_page_loads(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'accounts/login.html')

    def test_login_success(self):
        resp = self.client.post(self.url, {
            'username': 'testuser',
            'password': 'testpass123',
        })
        self.assertRedirects(resp, reverse('file_list'))

    def test_login_wrong_password(self):
        resp = self.client.post(self.url, {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '用户名或密码错误')

    def test_login_nonexistent_user(self):
        resp = self.client.post(self.url, {
            'username': 'nobody',
            'password': 'testpass123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '用户名或密码错误')

    def test_login_redirect_next(self):
        resp = self.client.post(f'{self.url}?next=/files/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        self.assertRedirects(resp, '/files/')

    def test_logout(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('logout'))
        self.assertRedirects(resp, reverse('login'))


class ProfileTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', email='test@example.com',
                                              password='testpass123')

    def test_profile_requires_login(self):
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 302)

    def test_profile_page_loads(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'accounts/profile.html')
        self.assertContains(resp, 'testuser')
        self.assertContains(resp, 'test@example.com')

    def test_profile_shows_zero_usage(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '0.0 B')
        self.assertContains(resp, '1.0 GB')
        self.assertContains(resp, '0.0%')


class CaptchaTests(TestCase):
    def setUp(self):
        from .captcha import generate_captcha, verify_captcha
        self.generate = generate_captcha
        self.verify = verify_captcha

    def test_generate_creates_session(self):
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/')
        from django.contrib.sessions.middleware import SessionMiddleware
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()

        q = self.generate(request)
        self.assertIn('?', q)
        self.assertIn('captcha_answer', request.session)

    def test_verify_correct(self):
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/')
        from django.contrib.sessions.middleware import SessionMiddleware
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()

        self.generate(request)
        answer = request.session['captcha_answer']
        self.assertTrue(self.verify(request, answer))

    def test_verify_incorrect(self):
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/')
        from django.contrib.sessions.middleware import SessionMiddleware
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()

        self.generate(request)
        self.assertFalse(self.verify(request, '99999'))

    def test_verify_consumes_session(self):
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/')
        from django.contrib.sessions.middleware import SessionMiddleware
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()

        self.generate(request)
        self.verify(request, request.session['captcha_answer'])
        self.assertNotIn('captcha_answer', request.session)


class SiteSettingsTests(TestCase):
    def test_singleton_behavior(self):
        from .models import SiteSettings
        s1 = SiteSettings.get_settings()
        s2 = SiteSettings.get_settings()
        self.assertEqual(s1.pk, s2.pk)
        self.assertEqual(s1.pk, 1)

    def test_default_values(self):
        from .models import SiteSettings
        s = SiteSettings.get_settings()
        self.assertTrue(s.allow_registration)
        self.assertFalse(s.require_captcha_register)
        self.assertFalse(s.require_captcha_login)


class UserGroupTests(TestCase):
    def test_create_group(self):
        from .models import UserGroup
        g = UserGroup.objects.create(name='VIP', storage_quota=2147483648)
        self.assertEqual(g.name, 'VIP')
        self.assertFalse(g.is_default)

    def test_default_unique(self):
        from .models import UserGroup
        g1 = UserGroup.objects.create(name='G1', is_default=True)
        g2 = UserGroup.objects.create(name='G2', is_default=True)
        g1.refresh_from_db()
        g2.refresh_from_db()
        self.assertTrue(g2.is_default)
        self.assertFalse(g1.is_default)  # G1 should have been unset

    def test_group_user_count(self):
        from .models import UserGroup, User
        g = UserGroup.objects.create(name='Dev', storage_quota=1073741824)
        u = User.objects.create_user('devuser', password='testpass123', group=g)
        self.assertEqual(g.users.count(), 1)


class RegistrationFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('register')

    def test_register_with_default_group(self):
        from .models import UserGroup, SiteSettings
        g = UserGroup.objects.create(name='Standard', storage_quota=524288000, is_default=True)
        s = SiteSettings.get_settings()
        s.default_group = g
        s.save()

        resp = self.client.post(self.url, {
            'username': 'newguy', 'password': 'testpass123', 'password2': 'testpass123',
        })
        self.assertRedirects(resp, reverse('file_list'))
        user = User.objects.get(username='newguy')
        self.assertEqual(user.group, g)
        self.assertEqual(user.storage_quota, 524288000)

    def test_register_when_disabled(self):
        from .models import SiteSettings
        s = SiteSettings.get_settings()
        s.allow_registration = False
        s.save()

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '关闭注册')

        resp = self.client.post(self.url, {
            'username': 'blocked', 'password': 'testpass123', 'password2': 'testpass123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='blocked').exists())


class AdminUserManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('adminuser', 'admin@test.com', 'admin123')
        self.user = User.objects.create_user('normal', password='testpass123')
        self.client.login(username='adminuser', password='admin123')

    def test_admin_user_list(self):
        resp = self.client.get(reverse('admin_user_list'))
        self.assertEqual(resp.status_code, 200)

    def test_admin_user_update_group(self):
        from .models import UserGroup
        g = UserGroup.objects.create(name='Platinum', storage_quota=107374182400)
        resp = self.client.post(
            reverse('admin_user_update', args=[self.user.id]),
            {'action': 'update_group', 'group': str(g.id)}
        )
        self.assertRedirects(resp, reverse('admin_user_list'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.group, g)
        self.assertEqual(self.user.storage_quota, g.storage_quota)

    def test_admin_user_update_remove_group(self):
        from .models import UserGroup
        g = UserGroup.objects.create(name='Temp')
        self.user.group = g
        self.user.save()
        resp = self.client.post(
            reverse('admin_user_update', args=[self.user.id]),
            {'action': 'update_group', 'group': ''}
        )
        self.user.refresh_from_db()
        self.assertIsNone(self.user.group)

    def test_toggle_admin_on(self):
        resp = self.client.post(
            reverse('admin_user_update', args=[self.user.id]),
            {'action': 'toggle_admin'}
        )
        self.assertRedirects(resp, reverse('admin_user_list'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)
        self.assertTrue(self.user.is_superuser)

    def test_toggle_admin_off_last_admin(self):
        # Try to remove admin from the only admin
        resp = self.client.post(
            reverse('admin_user_update', args=[self.admin.id]),
            {'action': 'toggle_admin'}
        )
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_superuser)  # should still be admin


class AdminGroupManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('admin2', 'a@t.com', 'admin123')
        self.client.login(username='admin2', password='admin123')

    def test_group_create(self):
        resp = self.client.post(reverse('admin_group_create'), {
            'name': 'NewGroup', 'quota': '52428800',
        })
        self.assertRedirects(resp, reverse('admin_group_list'))
        from .models import UserGroup
        self.assertTrue(UserGroup.objects.filter(name='NewGroup').exists())

    def test_group_edit(self):
        from .models import UserGroup
        g = UserGroup.objects.create(name='OldName', storage_quota=1000)
        resp = self.client.post(reverse('admin_group_edit', args=[g.id]), {
            'name': 'NewName', 'quota': '5000',
        })
        g.refresh_from_db()
        self.assertEqual(g.name, 'NewName')
        self.assertEqual(g.storage_quota, 5000)

    def test_group_delete(self):
        from .models import UserGroup
        g = UserGroup.objects.create(name='ToDelete', storage_quota=1000)
        resp = self.client.post(reverse('admin_group_delete', args=[g.id]))
        self.assertRedirects(resp, reverse('admin_group_list'))
        self.assertFalse(UserGroup.objects.filter(id=g.id).exists())

    def test_cannot_delete_default_group(self):
        from .models import UserGroup
        g = UserGroup.objects.create(name='DefaultGroup', is_default=True)
        resp = self.client.post(reverse('admin_group_delete', args=[g.id]))
        self.assertRedirects(resp, reverse('admin_group_list'))
        self.assertTrue(UserGroup.objects.filter(id=g.id).exists())

    def test_group_edit_quota_sync_users(self):
        from .models import UserGroup
        g = UserGroup.objects.create(name='SyncGroup', storage_quota=1000)
        u = User.objects.create_user('syncuser', password='testpass123', group=g, storage_quota=1000)
        resp = self.client.post(reverse('admin_group_edit', args=[g.id]), {
            'name': 'SyncGroup', 'quota': '9999',
        })
        u.refresh_from_db()
        self.assertEqual(u.storage_quota, 9999)
