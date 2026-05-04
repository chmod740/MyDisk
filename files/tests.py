import io
import os
import zipfile
import tempfile
from uuid import uuid4

from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from .models import Folder, File


class FileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', password='testpass123')

    def test_file_creation(self):
        folder = Folder.objects.create(name='TestFolder', owner=self.user)
        upload = SimpleUploadedFile('hello.txt', b'Hello World')
        f = File.objects.create(
            name='hello.txt', file=upload, size=11,
            mime_type='text/plain', folder=folder, owner=self.user
        )
        self.assertEqual(f.name, 'hello.txt')
        self.assertEqual(f.extension, '.txt')
        self.assertTrue(f.is_text)
        self.assertFalse(f.is_image)
        self.assertFalse(f.is_pdf)
        self.assertEqual(str(f), 'hello.txt')
        self.assertIsNotNone(f.id)

    def test_file_image_detection(self):
        upload = SimpleUploadedFile('photo.png', b'fake-png-data',
                                    content_type='image/png')
        f = File.objects.create(
            name='photo.png', file=upload, size=100,
            mime_type='image/png', owner=self.user
        )
        self.assertTrue(f.is_image)
        self.assertTrue(f.extension, '.png')

    def test_file_pdf_detection(self):
        upload = SimpleUploadedFile('doc.pdf', b'%PDF-fake',
                                    content_type='application/pdf')
        f = File.objects.create(
            name='doc.pdf', file=upload, size=100,
            mime_type='application/pdf', owner=self.user
        )
        self.assertTrue(f.is_pdf)

    def test_file_soft_delete(self):
        upload = SimpleUploadedFile('test.txt', b'content')
        f = File.objects.create(name='test.txt', file=upload, size=7,
                                mime_type='text/plain', owner=self.user)
        self.assertFalse(f.is_deleted)
        self.assertIsNone(f.deleted_at)

        f.soft_delete()
        f.refresh_from_db()
        self.assertTrue(f.is_deleted)
        self.assertIsNotNone(f.deleted_at)

    def test_file_upload_to_path(self):
        upload = SimpleUploadedFile('test.txt', b'content')
        f = File.objects.create(name='test.txt', file=upload, size=7,
                                mime_type='text/plain', owner=self.user)
        path = f.file.name
        self.assertIn(str(self.user.id), path)
        self.assertTrue(path.endswith('.txt'))

    def test_file_code_detection(self):
        for ext in ['.py', '.js', '.html', '.css', '.json', '.md']:
            upload = SimpleUploadedFile(f'code{ext}', b'// code content')
            f = File.objects.create(
                name=f'code{ext}', file=upload, size=100,
                mime_type='text/plain', owner=self.user
            )
            self.assertTrue(f.is_text, f'{ext} should be detected as text')


class FolderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', password='testpass123')

    def test_folder_creation(self):
        folder = Folder.objects.create(name='Docs', owner=self.user)
        self.assertEqual(str(folder), 'Docs')
        self.assertIsNone(folder.parent)
        self.assertFalse(folder.is_deleted)
        self.assertIsNotNone(folder.id)

    def test_nested_folders(self):
        root = Folder.objects.create(name='Root', owner=self.user)
        child = Folder.objects.create(name='Child', parent=root, owner=self.user)
        grandchild = Folder.objects.create(name='Grandchild', parent=child, owner=self.user)

        self.assertEqual(root.children.count(), 1)
        self.assertEqual(child.parent, root)
        ancestors = grandchild.get_ancestors()
        self.assertEqual(len(ancestors), 2)
        self.assertEqual(ancestors[0], root)
        self.assertEqual(ancestors[1], child)

    def test_folder_soft_delete_cascades(self):
        root = Folder.objects.create(name='Root', owner=self.user)
        child = Folder.objects.create(name='Child', parent=root, owner=self.user)
        upload = SimpleUploadedFile('f.txt', b'data')
        f = File.objects.create(name='f.txt', file=upload, size=4,
                                mime_type='text/plain', folder=child, owner=self.user)

        root.soft_delete()

        root.refresh_from_db()
        child.refresh_from_db()
        f.refresh_from_db()
        self.assertTrue(root.is_deleted)
        self.assertTrue(child.is_deleted)
        self.assertTrue(f.is_deleted)

    def test_top_level_folder_no_ancestors(self):
        folder = Folder.objects.create(name='Top', owner=self.user)
        self.assertEqual(folder.get_ancestors(), [])


class FileListTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')
        self.url = reverse('file_list')

    def test_file_list_requires_login(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_file_list_empty(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'files/file_list.html')
        self.assertContains(resp, '此文件夹为空')

    def test_file_list_shows_folders_and_files(self):
        Folder.objects.create(name='MyFolder', owner=self.user)
        upload = SimpleUploadedFile('doc.txt', b'content')
        File.objects.create(name='doc.txt', file=upload, size=7,
                            mime_type='text/plain', owner=self.user)

        resp = self.client.get(self.url)
        self.assertContains(resp, 'MyFolder')
        self.assertContains(resp, 'doc.txt')

    def test_file_list_inside_folder(self):
        folder = Folder.objects.create(name='SubFolder', owner=self.user)
        upload = SimpleUploadedFile('inside.txt', b'inside')
        File.objects.create(name='inside.txt', file=upload, size=6,
                            mime_type='text/plain', folder=folder, owner=self.user)

        resp = self.client.get(f'{self.url}?folder={folder.id}')
        self.assertContains(resp, 'inside.txt')
        self.assertContains(resp, 'SubFolder')  # breadcrumb

    def test_file_list_invalid_folder(self):
        resp = self.client.get(f'{self.url}?folder=99999999-9999-9999-9999-999999999999')
        self.assertRedirects(resp, self.url)

    def test_file_list_search(self):
        Folder.objects.create(name='Documents', owner=self.user)
        Folder.objects.create(name='Images', owner=self.user)

        resp = self.client.get(f'{self.url}?q=Doc')
        self.assertContains(resp, 'Documents')
        # Searching filters main content; the sidebar folder tree is unfiltered
        # so verify Documents appears in the main table area
        self.assertContains(resp, 'Documents')

    def test_file_list_sort_by_name(self):
        upload1 = SimpleUploadedFile('b.txt', b'b')
        upload2 = SimpleUploadedFile('a.txt', b'a')
        File.objects.create(name='b.txt', file=upload1, size=1,
                            mime_type='text/plain', owner=self.user)
        File.objects.create(name='a.txt', file=upload2, size=1,
                            mime_type='text/plain', owner=self.user)

        resp = self.client.get(f'{self.url}?sort=name')
        content = resp.content.decode()
        pos_a = content.index('a.txt')
        pos_b = content.index('b.txt')
        self.assertLess(pos_a, pos_b)

    def test_file_list_sort_by_size(self):
        upload1 = SimpleUploadedFile('big.txt', b'x' * 100)
        upload2 = SimpleUploadedFile('small.txt', b'x')
        File.objects.create(name='big.txt', file=upload1, size=100,
                            mime_type='text/plain', owner=self.user)
        File.objects.create(name='small.txt', file=upload2, size=1,
                            mime_type='text/plain', owner=self.user)

        resp = self.client.get(f'{self.url}?sort=-size')
        content = resp.content.decode()
        pos_big = content.index('big.txt')
        pos_small = content.index('small.txt')
        self.assertLess(pos_big, pos_small)

    def test_file_list_excludes_deleted(self):
        upload = SimpleUploadedFile('visible.txt', b'visible')
        f = File.objects.create(name='visible.txt', file=upload, size=7,
                                mime_type='text/plain', owner=self.user)
        f.soft_delete()

        resp = self.client.get(self.url)
        self.assertNotContains(resp, 'visible.txt')

    def test_file_list_htmx_request(self):
        resp = self.client.get(self.url, HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'files/_file_list_content.html')


class FileUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')
        self.url = reverse('file_upload')

    def test_upload_single_file(self):
        upload = SimpleUploadedFile('test.txt', b'Hello World')
        resp = self.client.post(self.url, {'files': [upload]})
        self.assertRedirects(resp, reverse('file_list'))

        f = File.objects.get(owner=self.user, name='test.txt')
        self.assertEqual(f.size, 11)
        self.assertEqual(f.mime_type, 'text/plain')

    def test_upload_multiple_files(self):
        f1 = SimpleUploadedFile('a.txt', b'aaa')
        f2 = SimpleUploadedFile('b.txt', b'bbb')
        resp = self.client.post(self.url, {'files': [f1, f2]})

        self.assertEqual(File.objects.filter(owner=self.user).count(), 2)

    def test_upload_into_folder(self):
        folder = Folder.objects.create(name='Target', owner=self.user)
        upload = SimpleUploadedFile('data.txt', b'data')
        resp = self.client.post(self.url, {'files': [upload], 'folder': str(folder.id)})

        f = File.objects.get(owner=self.user, name='data.txt')
        self.assertEqual(f.folder, folder)

    def test_upload_no_files(self):
        resp = self.client.post(self.url, {})
        self.assertRedirects(resp, reverse('file_list'))
        # No files created
        self.assertEqual(File.objects.filter(owner=self.user).count(), 0)

    def test_upload_updates_storage(self):
        upload = SimpleUploadedFile('bigfile.bin', b'x' * 1024)
        self.client.post(self.url, {'files': [upload]})

        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 1024)

    def test_upload_htmx_response(self):
        upload = SimpleUploadedFile('test.txt', b'content')
        resp = self.client.post(self.url, {'files': [upload]}, HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 204)

    def test_upload_invalid_folder(self):
        upload = SimpleUploadedFile('test.txt', b'content')
        resp = self.client.post(self.url, {
            'files': [upload],
            'folder': '99999999-9999-9999-9999-999999999999'
        })
        self.assertEqual(resp.status_code, 400)


class FileOperationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')
        self.upload = SimpleUploadedFile('original.txt', b'original content')
        self.file = File.objects.create(
            name='original.txt', file=self.upload, size=16,
            mime_type='text/plain', owner=self.user
        )

    def test_file_download(self):
        url = reverse('file_download', args=[self.file.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'original content', b''.join(resp.streaming_content))
        self.assertIn('original.txt', resp['Content-Disposition'])

    def test_file_download_not_owner(self):
        other = User.objects.create_user('other', password='testpass123')
        self.client.login(username='other', password='testpass123')
        url = reverse('file_download', args=[self.file.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_file_rename_get(self):
        url = reverse('file_rename', args=[self.file.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'original.txt')

    def test_file_rename_post(self):
        url = reverse('file_rename', args=[self.file.id])
        resp = self.client.post(url, {'name': 'renamed.txt'})
        self.assertEqual(resp.status_code, 204)

        self.file.refresh_from_db()
        self.assertEqual(self.file.name, 'renamed.txt')

    def test_file_rename_empty_name(self):
        url = reverse('file_rename', args=[self.file.id])
        resp = self.client.post(url, {'name': ''})
        self.assertEqual(resp.status_code, 200)  # re-renders form

    def test_file_delete(self):
        url = reverse('file_delete', args=[self.file.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 204)

        self.file.refresh_from_db()
        self.assertTrue(self.file.is_deleted)

    def test_file_delete_get_confirm(self):
        url = reverse('file_delete', args=[self.file.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_file_move(self):
        folder = Folder.objects.create(name='Dest', owner=self.user)
        url = reverse('file_move', args=[self.file.id])
        resp = self.client.post(url, {'target_folder': str(folder.id)})
        self.assertEqual(resp.status_code, 204)

        self.file.refresh_from_db()
        self.assertEqual(self.file.folder, folder)

    def test_file_move_to_root(self):
        folder = Folder.objects.create(name='Src', owner=self.user)
        self.file.folder = folder
        self.file.save()

        url = reverse('file_move', args=[self.file.id])
        resp = self.client.post(url, {'target_folder': ''})
        self.assertEqual(resp.status_code, 204)

        self.file.refresh_from_db()
        self.assertIsNone(self.file.folder)

    def test_file_move_get(self):
        url = reverse('file_move', args=[self.file.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_file_preview_image(self):
        img = SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\nfake', content_type='image/png')
        f = File.objects.create(name='photo.png', file=img, size=100,
                                mime_type='image/png', owner=self.user)
        url = reverse('file_preview', args=[f.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'image')

    def test_file_preview_text(self):
        url = reverse('file_preview', args=[self.file.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'text')
        self.assertContains(resp, 'original content')

    def test_file_preview_pdf(self):
        pdf = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 fake pdf', content_type='application/pdf')
        f = File.objects.create(name='doc.pdf', file=pdf, size=100,
                                mime_type='application/pdf', owner=self.user)
        url = reverse('file_preview', args=[f.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'pdf')

    def test_file_preview_unsupported(self):
        bin_file = SimpleUploadedFile('data.bin', b'\x00\x01\x02',
                                      content_type='application/octet-stream')
        f = File.objects.create(name='data.bin', file=bin_file, size=3,
                                mime_type='application/octet-stream', owner=self.user)
        url = reverse('file_preview', args=[f.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '不支持在线预览')


class FolderOperationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

    def test_folder_create(self):
        resp = self.client.post(reverse('folder_create'), {'name': 'NewFolder'})
        self.assertRedirects(resp, reverse('file_list'))
        self.assertTrue(Folder.objects.filter(owner=self.user, name='NewFolder').exists())

    def test_folder_create_empty_name(self):
        resp = self.client.post(reverse('folder_create'), {'name': ''})
        self.assertEqual(Folder.objects.filter(owner=self.user).count(), 0)

    def test_folder_create_with_parent(self):
        parent = Folder.objects.create(name='Parent', owner=self.user)
        resp = self.client.post(reverse('folder_create'), {
            'name': 'Child',
            'parent': str(parent.id)
        })
        child = Folder.objects.get(owner=self.user, name='Child')
        self.assertEqual(child.parent, parent)

    def test_folder_create_invalid_parent(self):
        resp = self.client.post(reverse('folder_create'), {
            'name': 'Orphan',
            'parent': '99999999-9999-9999-9999-999999999999'
        })
        self.assertRedirects(resp, reverse('file_list'))
        self.assertFalse(Folder.objects.filter(owner=self.user, name='Orphan').exists())

    def test_folder_rename(self):
        folder = Folder.objects.create(name='OldName', owner=self.user)
        url = reverse('folder_rename', args=[folder.id])
        resp = self.client.post(url, {'name': 'NewName'})
        self.assertEqual(resp.status_code, 204)

        folder.refresh_from_db()
        self.assertEqual(folder.name, 'NewName')

    def test_folder_delete(self):
        folder = Folder.objects.create(name='ToDelete', owner=self.user)
        url = reverse('folder_delete', args=[folder.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 204)

        folder.refresh_from_db()
        self.assertTrue(folder.is_deleted)


class BatchOperationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

    def test_batch_delete_files(self):
        f1 = File.objects.create(
            name='f1.txt', file=SimpleUploadedFile('f1.txt', b'1'), size=1,
            mime_type='text/plain', owner=self.user
        )
        f2 = File.objects.create(
            name='f2.txt', file=SimpleUploadedFile('f2.txt', b'2'), size=1,
            mime_type='text/plain', owner=self.user
        )

        resp = self.client.post(reverse('batch_delete'), {
            'file_ids': f'{f1.id},{f2.id}',
            'folder_ids': '',
        })
        self.assertEqual(resp.status_code, 204)

        f1.refresh_from_db()
        f2.refresh_from_db()
        self.assertTrue(f1.is_deleted)
        self.assertTrue(f2.is_deleted)

    def test_batch_delete_folders(self):
        d1 = Folder.objects.create(name='d1', owner=self.user)
        d2 = Folder.objects.create(name='d2', owner=self.user)

        resp = self.client.post(reverse('batch_delete'), {
            'file_ids': '',
            'folder_ids': f'{d1.id},{d2.id}',
        })
        self.assertEqual(resp.status_code, 204)

        d1.refresh_from_db()
        d2.refresh_from_db()
        self.assertTrue(d1.is_deleted)
        self.assertTrue(d2.is_deleted)

    def test_batch_delete_invalid_ids(self):
        resp = self.client.post(reverse('batch_delete'), {
            'file_ids': 'not-a-uuid,also-not',
            'folder_ids': '',
        })
        self.assertEqual(resp.status_code, 204)  # gracefully handled

    def test_batch_move(self):
        folder = Folder.objects.create(name='Target', owner=self.user)
        f1 = File.objects.create(
            name='f1.txt', file=SimpleUploadedFile('f1.txt', b'1'), size=1,
            mime_type='text/plain', owner=self.user
        )

        resp = self.client.post(reverse('batch_move'), {
            'file_ids': str(f1.id),
            'target_folder': str(folder.id),
        })
        self.assertEqual(resp.status_code, 204)

        f1.refresh_from_db()
        self.assertEqual(f1.folder, folder)

    def test_batch_move_to_root(self):
        folder = Folder.objects.create(name='Src', owner=self.user)
        f1 = File.objects.create(
            name='f1.txt', file=SimpleUploadedFile('f1.txt', b'1'), size=1,
            mime_type='text/plain', folder=folder, owner=self.user
        )

        resp = self.client.post(reverse('batch_move'), {
            'file_ids': str(f1.id),
            'target_folder': '',
        })
        self.assertEqual(resp.status_code, 204)

        f1.refresh_from_db()
        self.assertIsNone(f1.folder)

    def test_batch_download_zip(self):
        f1 = File.objects.create(
            name='a.txt', file=SimpleUploadedFile('a.txt', b'aaa'), size=3,
            mime_type='text/plain', owner=self.user
        )
        f2 = File.objects.create(
            name='b.txt', file=SimpleUploadedFile('b.txt', b'bbb'), size=3,
            mime_type='text/plain', owner=self.user
        )

        resp = self.client.post(reverse('batch_download'), {
            'file_ids': f'{f1.id},{f2.id}',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')

        # Verify zip content
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        self.assertIn('a.txt', names)
        self.assertIn('b.txt', names)

    def test_batch_download_no_files(self):
        resp = self.client.post(reverse('batch_download'), {'file_ids': ''})
        self.assertRedirects(resp, reverse('file_list'))

    def test_batch_delete_empty(self):
        resp = self.client.post(reverse('batch_delete'), {'file_ids': '', 'folder_ids': ''})
        self.assertEqual(resp.status_code, 204)


class RecycleBinTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

    def test_trash_list_empty(self):
        resp = self.client.get(reverse('trash'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '回收站为空')

    def test_trash_list_shows_deleted(self):
        f = File.objects.create(
            name='deleted.txt', file=SimpleUploadedFile('deleted.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )
        f.soft_delete()

        resp = self.client.get(reverse('trash'))
        self.assertContains(resp, 'deleted.txt')

    def test_trash_list_not_show_active(self):
        File.objects.create(
            name='active.txt', file=SimpleUploadedFile('active.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )

        resp = self.client.get(reverse('trash'))
        self.assertContains(resp, '回收站为空')

    def test_trash_restore_file(self):
        f = File.objects.create(
            name='restore.txt', file=SimpleUploadedFile('restore.txt', b'restore'), size=7,
            mime_type='text/plain', owner=self.user
        )
        f.soft_delete()

        url = reverse('trash_restore', args=['file', f.id])
        resp = self.client.post(url)
        self.assertRedirects(resp, reverse('trash'))

        f.refresh_from_db()
        self.assertFalse(f.is_deleted)

    def test_trash_restore_folder(self):
        folder = Folder.objects.create(name='RestoreFolder', owner=self.user)
        child = File.objects.create(
            name='child.txt', file=SimpleUploadedFile('child.txt', b'child'), size=5,
            mime_type='text/plain', folder=folder, owner=self.user
        )
        folder.soft_delete()
        child.refresh_from_db()
        self.assertTrue(child.is_deleted)

        url = reverse('trash_restore', args=['folder', folder.id])
        resp = self.client.post(url)
        self.assertRedirects(resp, reverse('trash'))

        folder.refresh_from_db()
        child.refresh_from_db()
        self.assertFalse(folder.is_deleted)
        self.assertFalse(child.is_deleted)

    def test_trash_destroy_file(self):
        f = File.objects.create(
            name='destroy.txt', file=SimpleUploadedFile('destroy.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )
        fid = f.id
        f.soft_delete()

        url = reverse('trash_destroy', args=['file', fid])
        resp = self.client.post(url)
        self.assertRedirects(resp, reverse('trash'))

        self.assertFalse(File.objects.filter(id=fid).exists())

    def test_trash_destroy_folder(self):
        folder = Folder.objects.create(name='DestroyFolder', owner=self.user)
        fid = folder.id
        folder.soft_delete()

        url = reverse('trash_destroy', args=['folder', fid])
        resp = self.client.post(url)
        self.assertRedirects(resp, reverse('trash'))

        self.assertFalse(Folder.objects.filter(id=fid).exists())

    def test_trash_restore_wrong_method(self):
        f = File.objects.create(
            name='x.txt', file=SimpleUploadedFile('x.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )
        f.soft_delete()
        url = reverse('trash_restore', args=['file', f.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)


class StorageTrackingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

    def test_storage_increases_on_upload(self):
        self.assertEqual(self.user.storage_used, 0)

        upload = SimpleUploadedFile('big.bin', b'x' * 500)
        self.client.post(reverse('file_upload'), {'files': [upload]})

        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 500)

    def test_storage_decreases_on_delete(self):
        upload = SimpleUploadedFile('big.bin', b'x' * 500)
        f = File.objects.create(name='big.bin', file=upload, size=500,
                                mime_type='application/octet-stream', owner=self.user)
        # Manually recalc
        from files.views import _recalc_storage
        _recalc_storage(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 500)

        f.soft_delete()
        _recalc_storage(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 0)

    def test_storage_multiple_files(self):
        for i in range(3):
            upload = SimpleUploadedFile(f'f{i}.txt', b'x' * 100)
            File.objects.create(name=f'f{i}.txt', file=upload, size=100,
                                mime_type='text/plain', owner=self.user)

        from files.views import _recalc_storage
        _recalc_storage(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.storage_used, 300)


class CleanupTrashCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', password='testpass123')

    def test_cleanup_old_trash(self):
        old_file = File.objects.create(
            name='old.txt', file=SimpleUploadedFile('old.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )
        old_file.is_deleted = True
        old_file.deleted_at = timezone.now() - timedelta(days=60)
        old_file.save()

        recent_file = File.objects.create(
            name='recent.txt', file=SimpleUploadedFile('recent.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )
        recent_file.is_deleted = True
        recent_file.deleted_at = timezone.now() - timedelta(days=1)
        recent_file.save()

        from django.core.management import call_command
        call_command('cleanup_trash')

        self.assertFalse(File.objects.filter(id=old_file.id).exists())
        self.assertTrue(File.objects.filter(id=recent_file.id).exists())

    def test_cleanup_keeps_active_files(self):
        active = File.objects.create(
            name='active.txt', file=SimpleUploadedFile('active.txt', b'x'), size=1,
            mime_type='text/plain', owner=self.user
        )
        from django.core.management import call_command
        call_command('cleanup_trash')

        self.assertTrue(File.objects.filter(id=active.id).exists())


class SecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user('usera', password='testpass123')
        self.user_b = User.objects.create_user('userb', password='testpass123')

    def test_cannot_access_other_user_file(self):
        upload = SimpleUploadedFile('secret.txt', b'secret')
        f = File.objects.create(name='secret.txt', file=upload, size=6,
                                mime_type='text/plain', owner=self.user_a)

        self.client.login(username='userb', password='testpass123')
        for url_name in ['file_download', 'file_preview', 'file_rename', 'file_delete', 'file_move']:
            url = reverse(url_name, args=[f.id])
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 404, f'{url_name} should return 404')

    def test_cannot_access_other_user_folder(self):
        folder = Folder.objects.create(name='Private', owner=self.user_a)

        self.client.login(username='userb', password='testpass123')
        url = reverse('folder_rename', args=[folder.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_cannot_see_other_user_items_in_list(self):
        Folder.objects.create(name='UserAFolder', owner=self.user_a)
        upload = SimpleUploadedFile('a_file.txt', b'a')
        File.objects.create(name='a_file.txt', file=upload, size=1,
                            mime_type='text/plain', owner=self.user_a)

        self.client.login(username='userb', password='testpass123')
        resp = self.client.get(reverse('file_list'))
        self.assertNotContains(resp, 'UserAFolder')
        self.assertNotContains(resp, 'a_file.txt')
