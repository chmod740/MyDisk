import random
import io
import string
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def generate_captcha(request):
    """生成图片验证码，返回 PNG bytes，答案存入 session"""
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    request.session['captcha_answer'] = chars

    # 创建图片
    width, height = 130, 48
    img = Image.new('RGB', (width, height), color=(245, 245, 250))
    draw = ImageDraw.Draw(img)

    # 画干扰线
    for _ in range(3):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=(180, 180, 200), width=1)

    # 画干扰点
    for _ in range(60):
        x, y = random.randint(0, width - 1), random.randint(0, height - 1)
        draw.point((x, y), fill=(150, 150, 170))

    # 画文字
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 32)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
        except (IOError, OSError):
            font = ImageFont.load_default()

    for i, ch in enumerate(chars):
        x = 10 + i * 28 + random.randint(-3, 3)
        y = random.randint(3, 10)
        color = (random.randint(0, 80), random.randint(40, 120), random.randint(80, 180))
        draw.text((x, y), ch, fill=color, font=font)

    # 扭曲
    img = img.filter(ImageFilter.SMOOTH)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def verify_captcha(request, user_answer):
    correct = request.session.get('captcha_answer', '')
    request.session.pop('captcha_answer', None)
    return str(user_answer or '').strip().upper() == correct.upper()
