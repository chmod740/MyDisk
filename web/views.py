from django.shortcuts import render_to_response, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt

from web.models import User
# Create your views here.

@csrf_exempt
def login(req):
    if req.method == "GET":
        return render_to_response('login.html')
    else:
        username = req.POST.get('username', None)
        password = req.POST.get('password', None)
        users = User.objects.filter(username__exact=username, password__exact=password)
        if len(users) > 0:
            user = users[0]
        else:
            users = User.objects.filter(phone__exact=username, password__exact=password)
            if len(users)>0:
                user = users[0]
            else:
                user = User.objects.filter(email__exact=username, password__exact=password)
                if len(users) > 0:
                    user = users[0]
                else:
                    user = None
        if user is None:
            return render_to_response('login.html', {'msg': '用户名或者密码错误'})
        else:
            req.session['username'] = user.username
            return HttpResponseRedirect('index.html')
@csrf_exempt
def register(req):
    if req.method == 'GET':
        return render_to_response('register.html', {'msg': None})
    else:
        username = req.POST.get('username', None)
        password = req.POST.get('password', None)
        re_password = req.POST.get('re_password', None)
        if username is None or password is None or re_password is None:
            return render_to_response('register.html', {'msg': '参数错误'})
        if password != re_password:
            return render_to_response('register.html', {'msg': '两次输入的密码不一致'})
        users = User.objects.filter(username__exact=username)
        if len(users) > 0:
            return render_to_response('register.html', {'msg': '用户名已经存在'})
        user = User()
        user.username = username
        user.password = password
        user.save()
        return render_to_response('register.html', {'script': '<script>alert("注册成功！");</script>'})

def index(req):

    return render_to_response('index.html')

def logout(req):
    req.session.clear()
    return HttpResponseRedirect('login.html')