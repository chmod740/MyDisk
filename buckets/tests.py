import io
import os
import tempfile
import zipfile
from uuid import uuid4

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from accounts.models import User
from .models import Bucket, BucketFile, ApiKey


class BucketModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('buckettest', password='testpass123')

    def test_bucket_creation(self):
        b = Bucket.objects.create(name='my-bucket', owner=self.user)
        self.assertEqual(str(b), 'buckettest/my-bucket')
        self.assertFalse(b.is_public)
        self.assertEqual(b.file_count, 0)

    def test_bucket_public_flag(self):
        b = Bucket.objects.create(name='public-bucket', owner=self.user, is_public=True)
        self.assertTrue(b.is_public)

    def test_bucket_name_unique_per_owner(self):
        Bucket.objects.create(name='unique', owner=self.user)
        with self.assertRaises(Exception):
            Bucket.objects.create(name='unique', owner=self.user)

    def test_different_owners_same_name(self):
        other = User.objects.create_user('other', password='testpass123')
        b1 = Bucket.objects.create(name='shared-name', owner=self.user)
        b2 = Bucket.objects.create(name='shared-name', owner=other)
        self.assertEqual(Bucket.objects.filter(name='shared-name').count(), 2)

    def test_bucket_total_size(self):
        b = Bucket.objects.create(name='test', owner=self.user)
        f1 = BucketFile.objects.create(
            bucket=b, name='a.txt',
            file=SimpleUploadedFile('a.txt', b'hello'), size=5,
            mime_type='text/plain'
        )
        f2 = BucketFile.objects.create(
            bucket=b, name='b.txt',
            file=SimpleUploadedFile('b.txt', b'world'), size=5,
            mime_type='text/plain'
        )
        self.assertEqual(b.total_size, 10)

    def test_bucket_statistics_exclude_folder_placeholders(self):
        b = Bucket.objects.create(name='folders', owner=self.user)
        BucketFile.objects.create(
            bucket=b, name='.keep', folder_path='empty/',
            file=SimpleUploadedFile('.keep', b'.'), size=1,
            mime_type='application/x-directory',
        )
        self.assertEqual(b.file_count, 0)
        self.assertEqual(b.total_size, 0)


class BucketFileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('bftest', password='testpass123')
        self.bucket = Bucket.objects.create(name='files', owner=self.user)

    def test_bucket_file_creation(self):
        bf = BucketFile.objects.create(
            bucket=self.bucket, name='doc.txt',
            file=SimpleUploadedFile('doc.txt', b'content'), size=7,
            mime_type='text/plain'
        )
        self.assertEqual(str(bf), 'files/doc.txt')
        self.assertEqual(bf.extension, '.txt')
        self.assertTrue(bf.is_text)
        self.assertFalse(bf.is_image)

    def test_bucket_file_image(self):
        bf = BucketFile.objects.create(
            bucket=self.bucket, name='img.png',
            file=SimpleUploadedFile('img.png', b'fake', content_type='image/png'),
            size=4, mime_type='image/png'
        )
        self.assertTrue(bf.is_image)

    def test_bucket_file_name_unique_in_bucket(self):
        BucketFile.objects.create(
            bucket=self.bucket, name='dup.txt',
            file=SimpleUploadedFile('dup.txt', b'a'), size=1,
            mime_type='text/plain'
        )
        with self.assertRaises(Exception):
            BucketFile.objects.create(
                bucket=self.bucket, name='dup.txt',
                file=SimpleUploadedFile('dup.txt', b'b'), size=1,
                mime_type='text/plain'
            )


class ApiKeyModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('keytest', password='testpass123')

    def test_generate_key(self):
        raw, hashed, prefix = ApiKey.generate_key()
        self.assertTrue(raw.startswith('djd_'))
        self.assertEqual(len(raw), 47)  # 4 + 43
        self.assertEqual(len(prefix), 8)
        self.assertNotEqual(raw, hashed)

    def test_verify_key_success(self):
        raw, hashed, prefix = ApiKey.generate_key()
        key = ApiKey.objects.create(
            user=self.user, name='test-key',
            key_hash=hashed, prefix=prefix
        )
        result = ApiKey.verify_key(raw)
        self.assertEqual(result, key)

    def test_verify_key_wrong(self):
        raw, hashed, prefix = ApiKey.generate_key()
        ApiKey.objects.create(user=self.user, name='test-key', key_hash=hashed, prefix=prefix)
        result = ApiKey.verify_key('djd_wrong-key-value-here')
        self.assertIsNone(result)

    def test_verify_key_inactive(self):
        raw, hashed, prefix = ApiKey.generate_key()
        key = ApiKey.objects.create(
            user=self.user, name='inactive', key_hash=hashed, prefix=prefix,
            is_active=False
        )
        result = ApiKey.verify_key(raw)
        self.assertIsNone(result)

    def test_api_key_last_accessed_updated(self):
        raw, hashed, prefix = ApiKey.generate_key()
        ApiKey.objects.create(user=self.user, name='test', key_hash=hashed, prefix=prefix)
        self.assertIsNone(ApiKey.objects.first().last_accessed_at)


class BucketViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('viewtest', password='testpass123')
        self.other = User.objects.create_user('other', password='testpass123')
        self.client.login(username='viewtest', password='testpass123')

    def test_bucket_list_empty(self):
        resp = self.client.get(reverse('bucket_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'buckets/list.html')

    def test_bucket_create(self):
        resp = self.client.post(reverse('bucket_create'), {'name': 'test-bucket'})
        self.assertRedirects(resp, reverse('bucket_list'))
        self.assertTrue(Bucket.objects.filter(owner=self.user, name='test-bucket').exists())

    def test_bucket_create_public(self):
        resp = self.client.post(reverse('bucket_create'), {
            'name': 'public-bucket', 'is_public': 'on'
        })
        b = Bucket.objects.get(owner=self.user, name='public-bucket')
        self.assertTrue(b.is_public)

    def test_bucket_create_empty_name(self):
        resp = self.client.post(reverse('bucket_create'), {'name': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '桶名称不能为空')

    def test_bucket_create_duplicate(self):
        Bucket.objects.create(name='dup', owner=self.user)
        resp = self.client.post(reverse('bucket_create'), {'name': 'dup'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '已存在')

    def test_bucket_detail_private(self):
        b = Bucket.objects.create(name='private', owner=self.user)
        resp = self.client.get(reverse('bucket_detail', args=[b.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'buckets/detail.html')

    def test_bucket_detail_public_anonymous(self):
        b = Bucket.objects.create(name='pub', owner=self.user, is_public=True)
        self.client.logout()
        resp = self.client.get(reverse('bucket_detail', args=[b.id]))
        self.assertEqual(resp.status_code, 200)  # public, anyone can view

    def test_bucket_detail_private_anonymous(self):
        b = Bucket.objects.create(name='priv', owner=self.user, is_public=False)
        self.client.logout()
        resp = self.client.get(reverse('bucket_detail', args=[b.id]))
        self.assertEqual(resp.status_code, 302)  # redirect to login

    def test_bucket_detail_other_user(self):
        b = Bucket.objects.create(name='mine', owner=self.user, is_public=False)
        self.client.login(username='other', password='testpass123')
        resp = self.client.get(reverse('bucket_detail', args=[b.id]))
        self.assertRedirects(resp, reverse('bucket_list'))  # forbidden

    def test_bucket_delete(self):
        b = Bucket.objects.create(name='tmp', owner=self.user)
        resp = self.client.post(reverse('bucket_delete', args=[b.id]))
        self.assertRedirects(resp, reverse('bucket_list'))
        self.assertFalse(Bucket.objects.filter(id=b.id).exists())

    def test_bucket_delete_other_user(self):
        b = Bucket.objects.create(name='mine', owner=self.user)
        self.client.login(username='other', password='testpass123')
        resp = self.client.post(reverse('bucket_delete', args=[b.id]))
        self.assertEqual(resp.status_code, 404)


class BucketFileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('ftest', password='testpass123')
        self.client.login(username='ftest', password='testpass123')
        self.bucket = Bucket.objects.create(name='test-bucket', owner=self.user)

    def test_upload_file(self):
        upload = SimpleUploadedFile('data.bin', b'binary data')
        resp = self.client.post(
            reverse('bucket_file_upload', args=[self.bucket.id]),
            {'files': [upload]}
        )
        self.assertRedirects(resp, reverse('bucket_detail', args=[self.bucket.id]))
        self.assertEqual(BucketFile.objects.filter(bucket=self.bucket).count(), 1)

    def test_upload_multiple_files(self):
        f1 = SimpleUploadedFile('a.txt', b'a')
        f2 = SimpleUploadedFile('b.txt', b'b')
        self.client.post(
            reverse('bucket_file_upload', args=[self.bucket.id]),
            {'files': [f1, f2]}
        )
        self.assertEqual(BucketFile.objects.filter(bucket=self.bucket).count(), 2)

    def test_download_file(self):
        bf = BucketFile.objects.create(
            bucket=self.bucket, name='hello.txt',
            file=SimpleUploadedFile('hello.txt', b'Hello World'), size=11,
            mime_type='text/plain'
        )
        resp = self.client.get(
            reverse('bucket_file_download', args=[self.bucket.id, bf.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Hello World', b''.join(resp.streaming_content))

    def test_download_file_anonymous_public(self):
        self.bucket.is_public = True
        self.bucket.save()
        bf = BucketFile.objects.create(
            bucket=self.bucket, name='pub.txt',
            file=SimpleUploadedFile('pub.txt', b'public'), size=6,
            mime_type='text/plain'
        )
        self.client.logout()
        resp = self.client.get(
            reverse('bucket_file_download', args=[self.bucket.id, bf.id])
        )
        self.assertEqual(resp.status_code, 200)

    def test_download_file_anonymous_private(self):
        bf = BucketFile.objects.create(
            bucket=self.bucket, name='priv.txt',
            file=SimpleUploadedFile('priv.txt', b'private'), size=7,
            mime_type='text/plain'
        )
        self.client.logout()
        resp = self.client.get(
            reverse('bucket_file_download', args=[self.bucket.id, bf.id])
        )
        self.assertEqual(resp.status_code, 302)

    def test_markdown_editor_uses_shared_renderer_and_image_upload(self):
        bucket_file = BucketFile.objects.create(
            bucket=self.bucket, name='README.md', folder_path='docs/',
            file=SimpleUploadedFile('README.md', b'# Bucket editor'), size=15,
            mime_type='text/markdown',
        )

        resp = self.client.get(
            reverse('bucket_file_edit', args=[self.bucket.id, bucket_file.id])
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'js/markdown-editor.js')
        self.assertContains(resp, 'data-image-upload-url=')
        self.assertContains(resp, 'data-folder-path="docs/"')
        self.assertContains(resp, 'data-preview-theme')
        self.assertContains(resp, '# Bucket editor')

    def test_markdown_inline_preview_uses_shared_renderer(self):
        bucket_file = BucketFile.objects.create(
            bucket=self.bucket, name='inline.md',
            file=SimpleUploadedFile('inline.md', b'# Inline'), size=8,
            mime_type='text/markdown',
        )

        resp = self.client.get(
            reverse('bucket_file_preview', args=[self.bucket.id, bucket_file.id]),
            HTTP_HX_REQUEST='true',
        )

        self.assertTemplateUsed(resp, 'buckets/_preview_inline.html')
        self.assertContains(resp, 'DjangoDiskMarkdownRenderer.render(source, el)')
        self.assertNotContains(resp, 'marked.parse')

    def test_markdown_full_preview_has_style_selector(self):
        bucket_file = BucketFile.objects.create(
            bucket=self.bucket, name='styled.md',
            file=SimpleUploadedFile('styled.md', b'# Styled'), size=8,
            mime_type='text/markdown',
        )

        resp = self.client.get(
            reverse('bucket_file_preview', args=[self.bucket.id, bucket_file.id])
        )

        self.assertContains(resp, 'data-markdown-preview-shell')
        self.assertContains(resp, 'data-markdown-preview-theme')
        self.assertContains(resp, 'css/markdown-preview.css')
        self.assertContains(resp, 'js/markdown-preview.js')

    def test_delete_file(self):
        bf = BucketFile.objects.create(
            bucket=self.bucket, name='del.txt',
            file=SimpleUploadedFile('del.txt', b'x'), size=1,
            mime_type='text/plain'
        )
        resp = self.client.post(
            reverse('bucket_file_delete', args=[self.bucket.id, bf.id])
        )
        self.assertRedirects(resp, reverse('bucket_detail', args=[self.bucket.id]))
        self.assertFalse(BucketFile.objects.filter(id=bf.id).exists())

    def test_upload_no_files(self):
        resp = self.client.post(
            reverse('bucket_file_upload', args=[self.bucket.id]), {}
        )
        self.assertRedirects(resp, reverse('bucket_detail', args=[self.bucket.id]))


class BucketFolderDownloadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('foldertest', password='testpass123')
        self.other = User.objects.create_user('other-foldertest', password='testpass123')
        self.client.login(username='foldertest', password='testpass123')
        self.bucket = Bucket.objects.create(name='archive-bucket', owner=self.user)

    def _create_file(self, name, folder_path, content=b'data'):
        return BucketFile.objects.create(
            bucket=self.bucket, name=name, folder_path=folder_path,
            file=SimpleUploadedFile(name, content), size=len(content),
            mime_type='text/plain',
        )

    def test_download_uses_current_directory_name(self):
        self._create_file('report.txt', 'parent/current/')

        resp = self.client.get(
            reverse('bucket_folder_download', args=[self.bucket.id]),
            {'path': 'parent/current/'},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIn('filename="current.zip"', resp['Content-Disposition'])
        self.assertNotIn('parent.zip', resp['Content-Disposition'])

    def test_download_uses_paths_relative_to_current_directory(self):
        self._create_file('root.txt', 'parent/current/', b'root')
        self._create_file('nested.txt', 'parent/current/child/', b'nested')

        resp = self.client.get(
            reverse('bucket_folder_download', args=[self.bucket.id]),
            {'path': 'parent/current/'},
        )
        with zipfile.ZipFile(io.BytesIO(b''.join(resp.streaming_content))) as zf:
            names = zf.namelist()

        self.assertCountEqual(names, ['root.txt', 'child/nested.txt'])
        self.assertNotIn('current/root.txt', names)

    def test_root_download_uses_bucket_name_and_preserves_paths(self):
        self._create_file('root.txt', '', b'root')
        self._create_file('nested.txt', 'docs/', b'nested')

        resp = self.client.get(reverse('bucket_folder_download', args=[self.bucket.id]))
        with zipfile.ZipFile(io.BytesIO(b''.join(resp.streaming_content))) as zf:
            names = zf.namelist()

        self.assertEqual(resp.status_code, 200)
        self.assertIn('filename="archive-bucket.zip"', resp['Content-Disposition'])
        self.assertCountEqual(names, ['root.txt', 'docs/nested.txt'])

    def test_public_directory_download_allows_anonymous_access(self):
        self.bucket.is_public = True
        self.bucket.save(update_fields=['is_public'])
        self._create_file('public.txt', 'docs/')
        self.client.logout()

        resp = self.client.get(
            reverse('bucket_folder_download', args=[self.bucket.id]),
            {'path': 'docs/'},
        )

        self.assertEqual(resp.status_code, 200)

    def test_private_directory_download_rejects_other_user(self):
        self._create_file('private.txt', 'docs/')
        self.client.login(username='other-foldertest', password='testpass123')

        resp = self.client.get(
            reverse('bucket_folder_download', args=[self.bucket.id]),
            {'path': 'docs/'},
        )

        self.assertEqual(resp.status_code, 403)

    def test_empty_directory_download_returns_404(self):
        BucketFile.objects.create(
            bucket=self.bucket, name='.keep', folder_path='empty/',
            file=SimpleUploadedFile('.keep', b'.'), size=1,
            mime_type='application/x-directory',
        )

        resp = self.client.get(
            reverse('bucket_folder_download', args=[self.bucket.id]),
            {'path': 'empty/'},
        )

        self.assertEqual(resp.status_code, 404)


class StorageQuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('quotatest', password='testpass123')
        self.bucket = Bucket.objects.create(name='quota-bucket', owner=self.user)

    def test_storage_increases_on_bucket_upload(self):
        self.assertEqual(self.user.storage_used, 0)
        BucketFile.objects.create(
            bucket=self.bucket, name='big.bin',
            file=SimpleUploadedFile('big.bin', b'x' * 500), size=500,
            mime_type='application/octet-stream'
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 500)

    def test_storage_decreases_on_bucket_delete(self):
        bf = BucketFile.objects.create(
            bucket=self.bucket, name='big.bin',
            file=SimpleUploadedFile('big.bin', b'x' * 500), size=500,
            mime_type='application/octet-stream'
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 500)

        bf.file.delete(save=False)
        bf.delete()
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 0)

    def test_full_recalc_includes_bucket_files(self):
        BucketFile.objects.create(
            bucket=self.bucket, name='bf.bin',
            file=SimpleUploadedFile('bf.bin', b'x' * 300), size=300,
            mime_type='application/octet-stream'
        )
        from files.views import _recalc_storage
        _recalc_storage(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 300)

    def test_placeholder_does_not_consume_quota(self):
        BucketFile.objects.create(
            bucket=self.bucket, name='.keep', folder_path='empty/',
            file=SimpleUploadedFile('.keep', b'.'), size=1,
            mime_type='application/x-directory',
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 0)

    def test_bucket_upload_over_quota_is_rejected(self):
        self.user.storage_quota = 3
        self.user.save(update_fields=['storage_quota'])
        self.client.login(username='quotatest', password='testpass123')

        resp = self.client.post(
            reverse('bucket_file_upload', args=[self.bucket.id]),
            {'files': [SimpleUploadedFile('large.bin', b'1234')]},
        )

        self.assertEqual(resp.status_code, 413)
        self.assertFalse(BucketFile.objects.filter(bucket=self.bucket, name='large.bin').exists())

    def test_bucket_markdown_edit_updates_storage_delta(self):
        self.client.login(username='quotatest', password='testpass123')
        bucket_file = BucketFile.objects.create(
            bucket=self.bucket, name='README.md',
            file=SimpleUploadedFile('README.md', b'old'), size=3,
            mime_type='text/markdown',
        )

        resp = self.client.post(
            reverse('bucket_file_edit', args=[self.bucket.id, bucket_file.id]),
            {'content': 'new content'},
        )

        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 11)


class ApiKeyViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('apikeytest', password='testpass123')
        self.client.login(username='apikeytest', password='testpass123')
        self.bucket = Bucket.objects.create(name='api-bucket', owner=self.user)

    def test_api_key_list(self):
        resp = self.client.get(reverse('api_key_list'))
        self.assertEqual(resp.status_code, 200)

    def test_api_docs_requires_login(self):
        self.client.logout()

        resp = self.client.get(reverse('api_docs'))

        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp.url)

    def test_api_docs_lists_all_bucket_operations(self):
        resp = self.client.get(reverse('api_docs'))

        self.assertEqual(resp.status_code, 200)
        expected_operations = [
            '列出桶', '创建桶', '删除桶', '列出桶内文件', '上传文件',
            '下载桶文件', '删除桶文件', '创建目录', '删除目录',
        ]
        for operation in expected_operations:
            self.assertContains(resp, operation)
        self.assertContains(resp, '/buckets/api/buckets/&lt;bucket_id&gt;/files/')
        self.assertContains(resp, '/buckets/api/&lt;bucket_id&gt;/files/&lt;file_id&gt;/download/')

    def test_api_docs_contains_common_language_examples(self):
        resp = self.client.get(reverse('api_docs'))

        for language in [
            'cURL', 'JavaScript / TypeScript', 'Python', 'Go',
            'PHP', 'Java 11+', 'C# / .NET', 'Ruby',
        ]:
            self.assertContains(resp, language)
        self.assertContains(resp, 'X-Api-Key: djd_YOUR_API_KEY')

    def test_api_key_create(self):
        resp = self.client.post(reverse('api_key_create'), {'name': 'my-key'})
        self.assertRedirects(resp, reverse('api_key_list'))
        key = ApiKey.objects.get(user=self.user, name='my-key')
        self.assertTrue(key.is_active)
        self.assertEqual(len(key.prefix), 8)
        self.assertTrue(key.prefix.startswith('djd_'))

    def test_api_key_revoke(self):
        raw, hashed, prefix = ApiKey.generate_key()
        key = ApiKey.objects.create(user=self.user, name='revoke-me', key_hash=hashed, prefix=prefix)
        resp = self.client.post(reverse('api_key_revoke', args=[key.id]))
        self.assertRedirects(resp, reverse('api_key_list'))
        key.refresh_from_db()
        self.assertFalse(key.is_active)

    def test_api_download_with_key(self):
        raw, hashed, prefix = ApiKey.generate_key()
        key = ApiKey.objects.create(user=self.user, name='dl-key', key_hash=hashed, prefix=prefix)

        bf = BucketFile.objects.create(
            bucket=self.bucket, name='secret.txt',
            file=SimpleUploadedFile('secret.txt', b'secret'), size=6,
            mime_type='text/plain'
        )
        resp = self.client.get(
            reverse('api_bucket_file_download', args=[self.bucket.id, bf.id]),
            HTTP_X_API_KEY=raw
        )
        self.assertEqual(resp.status_code, 200)

    def test_api_download_invalid_key(self):
        bf = BucketFile.objects.create(
            bucket=self.bucket, name='nope.txt',
            file=SimpleUploadedFile('nope.txt', b'nope'), size=4,
            mime_type='text/plain'
        )
        resp = self.client.get(
            reverse('api_bucket_file_download', args=[self.bucket.id, bf.id]),
            HTTP_X_API_KEY='djd_invalid-key'
        )
        self.assertEqual(resp.status_code, 403)

    def test_api_download_no_key(self):
        bf = BucketFile.objects.create(
            bucket=self.bucket, name='nokey.txt',
            file=SimpleUploadedFile('nokey.txt', b'x'), size=1,
            mime_type='text/plain'
        )
        resp = self.client.get(
            reverse('api_bucket_file_download', args=[self.bucket.id, bf.id])
        )
        self.assertEqual(resp.status_code, 401)


class BucketApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('bucket-api-user', password='testpass123')
        self.bucket = Bucket.objects.create(name='api', owner=self.user)
        self.raw_key, key_hash, prefix = ApiKey.generate_key()
        ApiKey.objects.create(
            user=self.user, name='bucket-api', key_hash=key_hash, prefix=prefix,
        )

    def test_api_upload_updates_usage(self):
        resp = self.client.post(
            reverse('api_bucket_file_upload', args=[self.bucket.id]),
            {'files': [SimpleUploadedFile('api.txt', b'12345')]},
            HTTP_X_API_KEY=self.raw_key,
        )

        self.assertEqual(resp.status_code, 201)
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 5)

    def test_api_upload_over_quota_is_atomic(self):
        self.user.storage_quota = 5
        self.user.save(update_fields=['storage_quota'])

        resp = self.client.post(
            reverse('api_bucket_file_upload', args=[self.bucket.id]),
            {
                'files': [
                    SimpleUploadedFile('a.txt', b'123'),
                    SimpleUploadedFile('b.txt', b'456'),
                ],
            },
            HTTP_X_API_KEY=self.raw_key,
        )

        self.assertEqual(resp.status_code, 413)
        self.assertEqual(BucketFile.objects.filter(bucket=self.bucket).count(), 0)

    def test_api_upload_conflict_creates_nothing(self):
        BucketFile.objects.create(
            bucket=self.bucket, name='exists.txt',
            file=SimpleUploadedFile('exists.txt', b'old'), size=3,
            mime_type='text/plain',
        )

        resp = self.client.post(
            reverse('api_bucket_file_upload', args=[self.bucket.id]),
            {
                'files': [
                    SimpleUploadedFile('new.txt', b'new'),
                    SimpleUploadedFile('exists.txt', b'replacement'),
                ],
            },
            HTTP_X_API_KEY=self.raw_key,
        )

        self.assertEqual(resp.status_code, 409)
        self.assertFalse(BucketFile.objects.filter(bucket=self.bucket, name='new.txt').exists())

    def test_api_rejects_unsafe_folder_paths(self):
        resp = self.client.post(
            reverse('api_bucket_file_upload', args=[self.bucket.id]),
            {
                'folder_path': '../escape/',
                'files': [SimpleUploadedFile('safe.txt', b'x')],
            },
            HTTP_X_API_KEY=self.raw_key,
        )
        self.assertEqual(resp.status_code, 400)

        resp = self.client.post(
            reverse('api_bucket_folder_create', args=[self.bucket.id]),
            data='{"name": "../escape"}', content_type='application/json',
            HTTP_X_API_KEY=self.raw_key,
        )
        self.assertEqual(resp.status_code, 400)


class BucketPhysicalFileLifecycleTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media_dir.cleanup)
        self.user = User.objects.create_user('bucket-lifecycle', password='testpass123')

    def test_bucket_cascade_removes_physical_files_after_commit(self):
        bucket = Bucket.objects.create(name='delete', owner=self.user)
        bucket_file = BucketFile.objects.create(
            bucket=bucket, name='delete.txt',
            file=SimpleUploadedFile('delete.txt', b'delete'), size=6,
            mime_type='text/plain',
        )
        path = bucket_file.file.path
        self.assertTrue(os.path.exists(path))

        with self.captureOnCommitCallbacks(execute=True):
            bucket.delete()

        self.assertFalse(os.path.exists(path))
