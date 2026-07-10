import io
import zipfile
from uuid import uuid4

from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from buckets.models import Bucket, BucketFile
from files.models import Folder, File
from .models import ShareLink


class ShareCreateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

    def _create_file(self):
        return File.objects.create(
            name='shareable.txt',
            file=SimpleUploadedFile('shareable.txt', b'content'),
            size=7, mime_type='text/plain', owner=self.user
        )

    def test_share_create_page_loads(self):
        resp = self.client.get(reverse('share_create'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'sharing/share_create.html')

    def test_create_share_link_for_file(self):
        f = self._create_file()
        resp = self.client.post(reverse('share_create'), {'file_id': str(f.id)})
        self.assertRedirects(resp, reverse('share_manage'))

        link = ShareLink.objects.get(owner=self.user)
        self.assertEqual(link.file, f)
        self.assertIsNone(link.folder)

    def test_create_share_link_for_folder(self):
        folder = Folder.objects.create(name='Public', owner=self.user)
        resp = self.client.post(reverse('share_create'), {'folder_id': str(folder.id)})
        self.assertRedirects(resp, reverse('share_manage'))

        link = ShareLink.objects.get(owner=self.user)
        self.assertEqual(link.folder, folder)
        self.assertIsNone(link.file)

    def test_create_share_with_password(self):
        f = self._create_file()
        resp = self.client.post(reverse('share_create'), {
            'file_id': str(f.id),
            'password': 'secret123',
        })
        link = ShareLink.objects.get(owner=self.user)
        self.assertIsNotNone(link.password)
        self.assertTrue(link.password)  # hashed

    def test_create_share_with_expiry(self):
        f = self._create_file()
        resp = self.client.post(reverse('share_create'), {
            'file_id': str(f.id),
            'expires_days': '7',
        })
        link = ShareLink.objects.get(owner=self.user)
        self.assertIsNotNone(link.expires_at)
        expected = timezone.now() + timedelta(days=7)
        self.assertAlmostEqual(
            link.expires_at.timestamp(), expected.timestamp(), delta=5
        )

    def test_create_share_with_invalid_expiry(self):
        f = self._create_file()
        resp = self.client.post(reverse('share_create'), {
            'file_id': str(f.id),
            'expires_days': 'abc',
        })
        link = ShareLink.objects.get(owner=self.user)
        self.assertIsNone(link.expires_at)  # invalid input → no expiry

    def test_create_share_with_zero_expiry(self):
        f = self._create_file()
        resp = self.client.post(reverse('share_create'), {
            'file_id': str(f.id),
            'expires_days': '0',
        })
        link = ShareLink.objects.get(owner=self.user)
        self.assertIsNone(link.expires_at)

    def test_create_share_with_negative_expiry(self):
        f = self._create_file()
        resp = self.client.post(reverse('share_create'), {
            'file_id': str(f.id),
            'expires_days': '-1',
        })
        link = ShareLink.objects.get(owner=self.user)
        self.assertIsNone(link.expires_at)

    def test_create_share_no_target(self):
        resp = self.client.post(reverse('share_create'), {})
        self.assertRedirects(resp, reverse('file_list'))
        self.assertEqual(ShareLink.objects.filter(owner=self.user).count(), 0)

    def test_create_share_other_user_file(self):
        other = User.objects.create_user('other', password='testpass123')
        f = File.objects.create(
            name='other.txt',
            file=SimpleUploadedFile('other.txt', b'x'),
            size=1, mime_type='text/plain', owner=other
        )
        resp = self.client.post(reverse('share_create'), {'file_id': str(f.id)})
        self.assertEqual(resp.status_code, 404)

    def test_create_share_no_password(self):
        f = self._create_file()
        resp = self.client.post(reverse('share_create'), {'file_id': str(f.id)})
        link = ShareLink.objects.get(owner=self.user)
        self.assertIsNone(link.password)

    def test_share_manage_page(self):
        resp = self.client.get(reverse('share_manage'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'sharing/share_manage.html')

    def test_share_delete(self):
        f = self._create_file()
        link = ShareLink.objects.create(file=f, owner=self.user)

        url = reverse('share_delete', args=[link.id])
        resp = self.client.post(url)
        self.assertRedirects(resp, reverse('share_manage'))
        self.assertFalse(ShareLink.objects.filter(id=link.id).exists())

    def test_share_delete_other_user(self):
        f = self._create_file()
        link = ShareLink.objects.create(file=f, owner=self.user)

        other = User.objects.create_user('other', password='testpass123')
        self.client.login(username='other', password='testpass123')

        url = reverse('share_delete', args=[link.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 404)


class ShareAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.client = Client()

    def _create_shared_file(self, **kwargs):
        f = File.objects.create(
            name='shared.txt',
            file=SimpleUploadedFile('shared.txt', b'shared content'),
            size=14, mime_type='text/plain', owner=self.user, **kwargs
        )
        return ShareLink.objects.create(file=f, owner=self.user)

    def test_access_share_file_page(self):
        link = self._create_shared_file()
        url = reverse('share_access', args=[link.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'sharing/share_file.html')

    def test_access_share_folder_page(self):
        folder = Folder.objects.create(name='SharedFolder', owner=self.user)
        link = ShareLink.objects.create(folder=folder, owner=self.user)
        url = reverse('share_access', args=[link.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'sharing/share_folder.html')

    def test_access_invalid_share_link(self):
        fake_id = uuid4()
        url = reverse('share_access', args=[fake_id])
        resp = self.client.get(url)
        self.assertTemplateUsed(resp, 'sharing/share_error.html')
        self.assertContains(resp, '分享链接无效')

    def test_access_expired_share(self):
        link = self._create_shared_file()
        link.expires_at = timezone.now() - timedelta(days=1)
        link.save()

        url = reverse('share_access', args=[link.id])
        resp = self.client.get(url)
        self.assertTemplateUsed(resp, 'sharing/share_error.html')
        self.assertContains(resp, '已过期')

    def test_view_count_increments(self):
        link = self._create_shared_file()
        url = reverse('share_access', args=[link.id])

        self.client.get(url)
        link.refresh_from_db()
        self.assertEqual(link.view_count, 1)

        self.client.get(url)
        link.refresh_from_db()
        self.assertEqual(link.view_count, 2)

    def test_share_password_required(self):
        link = self._create_shared_file()
        from django.contrib.auth.hashers import make_password
        link.password = make_password('secret')
        link.save()

        url = reverse('share_access', args=[link.id])
        resp = self.client.get(url)
        self.assertTemplateUsed(resp, 'sharing/share_password.html')

    def test_share_password_correct(self):
        link = self._create_shared_file()
        from django.contrib.auth.hashers import make_password
        link.password = make_password('secret')
        link.save()

        url = reverse('share_access', args=[link.id])
        resp = self.client.post(url, {'password': 'secret'})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'sharing/share_file.html')

    def test_share_password_incorrect(self):
        link = self._create_shared_file()
        from django.contrib.auth.hashers import make_password
        link.password = make_password('secret')
        link.save()

        url = reverse('share_access', args=[link.id])
        resp = self.client.post(url, {'password': 'wrong'})
        self.assertTemplateUsed(resp, 'sharing/share_password.html')
        self.assertContains(resp, '密码错误')

    def test_share_password_rate_limit(self):
        link = self._create_shared_file()
        from django.contrib.auth.hashers import make_password
        link.password = make_password('secret')
        link.save()
        url = reverse('share_access', args=[link.id])

        for _ in range(5):
            self.client.post(url, {'password': 'wrong'})
        resp = self.client.post(url, {'password': 'wrong'})

        self.assertEqual(resp.status_code, 429)

    def test_share_with_password_expires_at_none(self):
        """Permanent share with password, not expired"""
        link = self._create_shared_file()
        from django.contrib.auth.hashers import make_password
        link.password = make_password('test')
        link.expires_at = None
        link.save()

        url = reverse('share_access', args=[link.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'sharing/share_password.html')

    def test_share_folder_lists_contents(self):
        folder = Folder.objects.create(name='Public', owner=self.user)
        File.objects.create(
            name='inside.txt',
            file=SimpleUploadedFile('inside.txt', b'inside'), size=6,
            mime_type='text/plain', folder=folder, owner=self.user
        )
        Folder.objects.create(name='SubFolder', parent=folder, owner=self.user)
        link = ShareLink.objects.create(folder=folder, owner=self.user)

        url = reverse('share_access', args=[link.id])
        resp = self.client.get(url)
        self.assertContains(resp, 'inside.txt')
        self.assertContains(resp, 'SubFolder')

    def test_share_not_shows_deleted_files(self):
        folder = Folder.objects.create(name='Public', owner=self.user)
        f = File.objects.create(
            name='deleted.txt',
            file=SimpleUploadedFile('deleted.txt', b'x'), size=1,
            mime_type='text/plain', folder=folder, owner=self.user
        )
        f.is_deleted = True
        f.save()

        link = ShareLink.objects.create(folder=folder, owner=self.user)
        url = reverse('share_access', args=[link.id])
        resp = self.client.get(url)
        self.assertNotContains(resp, 'deleted.txt')

    def test_soft_deleted_file_revokes_share_link(self):
        link = self._create_shared_file()
        link.file.soft_delete()

        self.assertFalse(ShareLink.objects.filter(pk=link.pk).exists())
        resp = self.client.get(reverse('share_access', args=[link.id]))
        self.assertContains(resp, '分享链接无效')

    def test_deleted_target_is_rejected_defensively(self):
        link = self._create_shared_file()
        File.objects.filter(pk=link.file_id).update(is_deleted=True)

        resp = self.client.get(reverse('share_access', args=[link.id]))

        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, '分享内容已删除', status_code=404)

    def test_private_bucket_share_downloads_file(self):
        bucket = Bucket.objects.create(name='private', owner=self.user)
        bucket_file = BucketFile.objects.create(
            bucket=bucket, name='secret.txt',
            file=SimpleUploadedFile('secret.txt', b'secret'),
            size=6, mime_type='text/plain',
        )
        link = ShareLink.objects.create(bucket=bucket, owner=self.user)

        resp = self.client.get(
            reverse('share_access', args=[link.id]),
            {'dl_bucket_file': str(bucket_file.id)},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b''.join(resp.streaming_content), b'secret')

    def test_bucket_share_cannot_download_other_bucket_file(self):
        bucket = Bucket.objects.create(name='shared', owner=self.user)
        other_bucket = Bucket.objects.create(name='other', owner=self.user)
        other_file = BucketFile.objects.create(
            bucket=other_bucket, name='other.txt',
            file=SimpleUploadedFile('other.txt', b'other'),
            size=5, mime_type='text/plain',
        )
        link = ShareLink.objects.create(bucket=bucket, owner=self.user)

        resp = self.client.get(
            reverse('share_access', args=[link.id]),
            {'dl_bucket_file': str(other_file.id)},
        )

        self.assertEqual(resp.status_code, 404)

    def test_shared_folder_zip_is_recursive(self):
        folder = Folder.objects.create(name='Current', owner=self.user)
        child = Folder.objects.create(name='Child', parent=folder, owner=self.user)
        File.objects.create(
            name='root.txt', file=SimpleUploadedFile('root.txt', b'root'),
            size=4, mime_type='text/plain', folder=folder, owner=self.user,
        )
        File.objects.create(
            name='nested.txt', file=SimpleUploadedFile('nested.txt', b'nested'),
            size=6, mime_type='text/plain', folder=child, owner=self.user,
        )
        link = ShareLink.objects.create(folder=folder, owner=self.user)

        resp = self.client.get(
            reverse('share_access', args=[link.id]), {'download': 'zip'},
        )
        payload = b''.join(resp.streaming_content)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertCountEqual(archive.namelist(), ['root.txt', 'Child/nested.txt'])

    def test_markdown_share_uses_sanitized_rendering(self):
        markdown = File.objects.create(
            name='unsafe.md',
            file=SimpleUploadedFile('unsafe.md', b'<img src=x onerror=alert(1)>'),
            size=34, mime_type='text/markdown', owner=self.user,
        )
        link = ShareLink.objects.create(file=markdown, owner=self.user)

        resp = self.client.get(reverse('share_access', args=[link.id]))

        self.assertContains(resp, 'js/markdown-sanitize.js')
        self.assertContains(resp, 'window.setSanitizedMarkdownHtml')
        self.assertNotContains(resp, 'el.innerHTML = html')


class ShareLinkModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', password='testpass123')

    def test_share_target_property_file(self):
        f = File.objects.create(
            name='f.txt', file=SimpleUploadedFile('f.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )
        link = ShareLink.objects.create(file=f, owner=self.user)
        self.assertEqual(link.target, f)

    def test_share_target_property_folder(self):
        folder = Folder.objects.create(name='F', owner=self.user)
        link = ShareLink.objects.create(folder=folder, owner=self.user)
        self.assertEqual(link.target, folder)

    def test_share_not_expired_without_expiry(self):
        f = File.objects.create(
            name='f.txt', file=SimpleUploadedFile('f.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user,
        )
        link = ShareLink.objects.create(file=f, owner=self.user)
        self.assertFalse(link.is_expired)

    def test_share_requires_exactly_one_target(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ShareLink.objects.create(owner=self.user)

    def test_share_not_expired_future(self):
        f = File.objects.create(
            name='f.txt', file=SimpleUploadedFile('f.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )
        link = ShareLink.objects.create(
            file=f, owner=self.user,
            expires_at=timezone.now() + timedelta(days=30)
        )
        self.assertFalse(link.is_expired)

    def test_share_expired(self):
        f = File.objects.create(
            name='f.txt', file=SimpleUploadedFile('f.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )
        link = ShareLink.objects.create(
            file=f, owner=self.user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        self.assertTrue(link.is_expired)
