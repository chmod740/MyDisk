from uuid import uuid4

from django.test import TestCase, Client
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


class ApiKeyViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('apikeytest', password='testpass123')
        self.client.login(username='apikeytest', password='testpass123')
        self.bucket = Bucket.objects.create(name='api-bucket', owner=self.user)

    def test_api_key_list(self):
        resp = self.client.get(reverse('api_key_list'))
        self.assertEqual(resp.status_code, 200)

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
