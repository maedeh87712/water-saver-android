# -*- coding: utf-8 -*-
"""نسخه اندرویدی برنامه «هر قطره مهم است»"""
from datetime import datetime, timedelta
import sqlite3
import os

from kivy.app import App
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    def fa(text):
        return get_display(arabic_reshaper.reshape(str(text)))
except Exception:
    def fa(text):
        return str(text)

PRIMARY = (0.05, 0.36, 0.67, 1)
DARK = (0.03, 0.18, 0.38, 1)
BG = (0.95, 0.97, 0.99, 1)
GREEN = (0.16, 0.58, 0.32, 1)
ORANGE = (0.95, 0.55, 0.08, 1)
RED = (0.82, 0.18, 0.16, 1)
RATES = {'shower': 12, 'hand_wash': 6, 'laundry': 60,
         'dishes_hand': 20, 'dishes_machine': 15, 'watering': 10}
LIMIT = 150


def jalali_today():
    # نمایش تاریخ شمسی تقریبی مطابق ساختار نسخه دسکتاپ
    t = datetime.now()
    months = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند']
    weekdays = ['دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه','شنبه','یکشنبه']
    jy = t.year - 621 if t.month > 3 else t.year - 622
    jm = (t.month + 8) % 12
    if jm == 0: jm = 12
    return f"{weekdays[t.weekday()]}، {t.day} {months[jm-1]} {jy}"


def calc(data):
    total = data['shower'] * RATES['shower'] + data['hand_wash'] * RATES['hand_wash']
    total += RATES['laundry'] if data['laundry'] else 0
    total += RATES['dishes_hand'] if data['dishes_type'] == 'hand' else RATES['dishes_machine']
    total += data['watering'] * RATES['watering']
    saving, waste = max(0, LIMIT-total), max(0, total-LIMIT)
    status = 'excellent' if total <= 100 else 'good' if total <= 150 else 'warning' if total <= 200 else 'danger'
    return {'total': round(total, 1), 'saving': round(saving, 1), 'waste': round(waste, 1), 'status': status}


class DB:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as c:
            c.execute('''CREATE TABLE IF NOT EXISTS daily_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL UNIQUE,
                shower_minutes REAL DEFAULT 0, hand_wash_count INTEGER DEFAULT 0,
                laundry_done INTEGER DEFAULT 0, dishes_type TEXT DEFAULT 'hand',
                watering_minutes REAL DEFAULT 0, total_usage REAL DEFAULT 0,
                saving REAL DEFAULT 0, points INTEGER DEFAULT 0, status TEXT DEFAULT 'good')''')
            c.execute('''CREATE TABLE IF NOT EXISTS challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT,
                points INTEGER DEFAULT 10, completed INTEGER DEFAULT 0, completion_date TEXT)''')
            for row in [('🚿 حمام کوتاه','زمان حمام را به کمتر از ۵ دقیقه برسانید',15),
                        ('🚰 شیر بسته','هنگام مسواک زدن شیر آب را ببندید',10)]:
                c.execute('INSERT OR IGNORE INTO challenges (name,description,points) VALUES (?,?,?)', row)

    def save(self, data, result):
        points = int(result['saving']/5) if result['saving'] > 0 else 0
        with sqlite3.connect(self.path) as c:
            c.execute('''INSERT OR REPLACE INTO daily_usage
                (date,shower_minutes,hand_wash_count,laundry_done,dishes_type,watering_minutes,total_usage,saving,points,status)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (datetime.now().strftime('%Y-%m-%d'), data['shower'], data['hand_wash'], int(data['laundry']),
                 data['dishes_type'], data['watering'], result['total'], result['saving'], points, result['status']))
        return points

    def stats(self):
        with sqlite3.connect(self.path) as c:
            row = c.execute('SELECT COALESCE(SUM(points),0),COALESCE(SUM(saving),0),COALESCE(AVG(total_usage),0) FROM daily_usage').fetchone()
            challenge = c.execute('SELECT COALESCE(SUM(points),0) FROM challenges WHERE completed=1').fetchone()[0]
        return row[0]+challenge, row[1], row[2]

    def weekly(self):
        with sqlite3.connect(self.path) as c:
            return c.execute('SELECT date,total_usage,saving,points,status FROM daily_usage ORDER BY date DESC LIMIT 7').fetchall()


class Card(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(14)
        self.spacing = dp(7)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        self.bind(pos=self._sync, size=self._sync)
    def _sync(self, *_):
        self.rect.pos, self.rect.size = self.pos, self.size


class WaterSaver(App):
    def build(self):
        self.title = 'هر قطره مهم است'
        Window.clearcolor = BG
        self.db = DB(os.path.join(self.user_data_dir, 'water_saver.db'))
        self.sm = ScreenManager(transition=FadeTransition())
        for name, maker in [('home', self.home), ('usage', self.usage), ('education', self.education), ('reports', self.reports)]:
            screen = Screen(name=name)
            root = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
            root.add_widget(self.header())
            body = maker()
            root.add_widget(body)
            root.add_widget(self.nav())
            screen.add_widget(root)
            self.sm.add_widget(screen)
        return self.sm

    def label(self, text, size=16, color=DARK, height=None, bold=False):
        return Label(text=fa(text), font_size=sp(size), color=color, size_hint_y=None,
                     height=dp(height or max(38, size*2.2)), halign='center', valign='middle', bold=bold,
                     text_size=(Window.width-dp(38), None))

    def header(self):
        box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(112), padding=dp(8), spacing=dp(2))
        with box.canvas.before:
            Color(*DARK); box.bg = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(16)])
        box.bind(pos=lambda w,*a: setattr(w.bg,'pos',w.pos), size=lambda w,*a: setattr(w.bg,'size',w.size))
        box.add_widget(self.label('💧 هر قطره مهم است', 23, (1,1,1,1), 48, True))
        box.add_widget(self.label('صرفه‌جویی در مصرف آب، مسئولیت اجتماعی', 13, (0.78,0.9,1,1), 30))
        box.add_widget(self.label(jalali_today(), 12, (1,1,1,1), 24))
        return box

    def nav(self):
        bar = GridLayout(cols=4, size_hint_y=None, height=dp(54), spacing=dp(5))
        for title, target in [('خانه','home'),('ثبت مصرف','usage'),('آموزش','education'),('گزارش','reports')]:
            bar.add_widget(self.btn(title, lambda _, t=target: self.go(t), PRIMARY, 12))
        return bar

    def btn(self, text, callback, color=PRIMARY, size=15):
        b = Button(text=fa(text), font_size=sp(size), bold=True, color=(1,1,1,1),
                   background_normal='', background_color=color, size_hint_y=None, height=dp(48))
        b.bind(on_release=callback)
        return b

    def go(self, name):
        self.sm.current = name
        if name in ('home','reports'):
            self.refresh_screen(name)

    def refresh_screen(self, name):
        old = self.sm.get_screen(name)
        root = old.children[0]
        root.remove_widget(root.children[1])
        root.add_widget(self.home() if name == 'home' else self.reports(), index=1)

    def scroll_body(self):
        scroll = ScrollView(do_scroll_x=False)
        box = BoxLayout(orientation='vertical', spacing=dp(10), padding=[dp(4),dp(8)], size_hint_y=None)
        box.bind(minimum_height=box.setter('height'))
        scroll.add_widget(box)
        return scroll, box

    def home(self):
        scroll, box = self.scroll_body()
        points, saved, avg = self.db.stats()
        box.add_widget(self.label('به اپلیکیشن نجات آب خوش آمدید!', 20, PRIMARY, 58, True))
        card = Card(size_hint_y=None, height=dp(220))
        card.add_widget(self.label('💧', 58, PRIMARY, 78))
        card.add_widget(self.label(f'🏆 امتیاز کل: {points:,}', 18, DARK, 40, True))
        card.add_widget(self.label(f'💧 آب نجات داده‌شده: {saved:,.0f} لیتر', 16, GREEN, 38))
        card.add_widget(self.label(f'📊 میانگین مصرف: {avg:.1f} لیتر', 16, DARK, 38))
        box.add_widget(card)
        quote = Card(size_hint_y=None, height=dp(105))
        quote.add_widget(self.label('«کُلُوا وَاشْرَبُوا وَلَا تُسْرِفُوا»', 18, GREEN, 40, True))
        quote.add_widget(self.label('(اعراف: ۳۱) خوردن و آشامیدن کنید و اسراف نکنید', 13, GREEN, 35))
        box.add_widget(quote)
        box.add_widget(self.btn('ثبت مصرف امروز', lambda *_: self.go('usage'), GREEN))
        return scroll

    def usage(self):
        scroll, box = self.scroll_body()
        box.add_widget(self.label('📊 ثبت مصرف روزانه آب', 21, PRIMARY, 50, True))
        self.fields = {}
        for key, title, default in [('shower','🚿 مدت حمام (دقیقه)', '10'), ('hand_wash','🤲 دفعات شستشوی دست','5'), ('watering','🌱 مدت آبیاری (دقیقه)','5')]:
            row = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(8))
            row.add_widget(self.label(title, 14, DARK, 48))
            inp = TextInput(text=default, multiline=False, input_filter='float', halign='center', font_size=sp(17), size_hint_x=.38)
            self.fields[key] = inp
            row.add_widget(inp); box.add_widget(row)
        box.add_widget(self.label('آیا امروز لباسشویی داشتید؟', 15, DARK, 38, True))
        self.laundry = ToggleButton(text=fa('بله'), state='down', group='laundry', size_hint_y=None, height=dp(45))
        no = ToggleButton(text=fa('خیر'), group='laundry', size_hint_y=None, height=dp(45))
        choices = GridLayout(cols=2, size_hint_y=None, height=dp(45), spacing=dp(8)); choices.add_widget(self.laundry); choices.add_widget(no)
        self.laundry_no = no; box.add_widget(choices)
        box.add_widget(self.label('نوع شست‌وشوی ظروف', 15, DARK, 38, True))
        self.dishes = Spinner(text=fa('دستی'), values=[fa('دستی'),fa('ماشین ظرفشویی')], size_hint_y=None, height=dp(48))
        box.add_widget(self.dishes)
        box.add_widget(self.btn('محاسبه و ذخیره نتیجه', self.calculate, ORANGE, 16))
        box.add_widget(self.label('حد استاندارد روزانه: ۱۵۰ لیتر', 13, DARK, 36))
        return scroll

    def calculate(self, *_):
        try:
            data = {k: float(v.text or 0) for k,v in self.fields.items()}
            data['laundry'] = self.laundry.state == 'down'
            data['dishes_type'] = 'hand' if self.dishes.text == fa('دستی') else 'machine'
            result = calc(data)
            points = self.db.save(data, result)
            if result['saving'] > 0:
                msg = f"آفرین! {result['total']} لیتر مصرف داشتید.\n{result['saving']} لیتر کمتر از حد استاندارد مصرف کردید.\nامتیاز کسب‌شده: {points}"
                color = GREEN
            else:
                msg = f"مصرف امروز: {result['total']} لیتر\n{result['waste']} لیتر بیشتر از حد استاندارد مصرف کرده‌اید."
                color = ORANGE
            content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(12))
            content.add_widget(self.label(msg, 17, color, 110, True))
            content.add_widget(self.btn('متوجه شدم', lambda *_: popup.dismiss(), PRIMARY))
            popup = Popup(title=fa('نتیجه محاسبه'), content=content, size_hint=(.88,.42))
            popup.open()
        except Exception:
            self.alert('لطفاً برای همه موارد، عدد معتبر وارد کنید.')

    def alert(self, text):
        Popup(title=fa('پیام'), content=self.label(text, 16, DARK, 90), size_hint=(.85,.3)).open()

    def education(self):
        scroll, box = self.scroll_body()
        box.add_widget(self.label('📚 آموزش نجات آب', 21, PRIMARY, 50, True))
        tips = [
            ('🚿 در حمام','زمان دوش را به ۵ دقیقه محدود کنید.\nهنگام شامپو زدن شیر آب را ببندید.'),
            ('🚰 در آشپزخانه','ماشین ظرفشویی را کامل پر کنید.\nسبزیجات را در ظرف بشویید.'),
            ('👕 در لباسشویی','ماشین لباسشویی را کامل پر کنید.\nاز برنامه اقتصادی استفاده کنید.'),
            ('🌱 در باغچه','گیاهان را صبح زود آبیاری کنید.\nاز سیستم آبیاری قطره‌ای استفاده کنید.')]
        for title, body in tips:
            card = Card(size_hint_y=None, height=dp(125))
            card.add_widget(self.label(title, 17, PRIMARY, 38, True))
            card.add_widget(self.label(body, 14, DARK, 68))
            box.add_widget(card)
        return scroll

    def reports(self):
        scroll, box = self.scroll_body()
        box.add_widget(self.label('📈 گزارش عملکرد هفتگی', 21, PRIMARY, 50, True))
        rows = self.db.weekly()
        if not rows:
            box.add_widget(self.label('هنوز داده‌ای ثبت نکرده‌اید!\nابتدا از بخش ثبت مصرف استفاده کنید.', 17, DARK, 110))
            return scroll
        total_usage = sum(r[1] for r in rows); total_saving = sum(r[2] for r in rows)
        points = sum(r[3] for r in rows); avg = total_usage/len(rows)
        good = sum(1 for r in rows if r[1] <= LIMIT); progress = good/len(rows)*100
        card = Card(size_hint_y=None, height=dp(190))
        for line in [f'میانگین مصرف: {avg:.1f} لیتر', f'کل صرفه‌جویی: {total_saving:.0f} لیتر',
                     f'امتیاز این هفته: {points}', f'روزهای با مصرف استاندارد: {good} از {len(rows)}',
                     f'نمره عملکرد: {progress:.0f}٪', f'حد استاندارد: {LIMIT} لیتر']:
            card.add_widget(self.label(line, 14, DARK, 27))
        box.add_widget(card)
        box.add_widget(self.label('📋 جزئیات ۷ روز اخیر', 18, PRIMARY, 42, True))
        for date, usage, saving, pts, status in rows:
            status_fa = {'excellent':'عالی ⭐','good':'خوب 👍','warning':'هشدار ⚠️','danger':'نیاز به بهبود'}.get(status,'-')
            c = Card(size_hint_y=None, height=dp(112))
            c.add_widget(self.label(date, 13, DARK, 25, True))
            c.add_widget(self.label(f'مصرف: {usage:.1f} لیتر   |   صرفه‌جویی: {saving:.1f} لیتر', 13, DARK, 28))
            c.add_widget(self.label(f'امتیاز: {pts}   |   وضعیت: {status_fa}', 13, GREEN if usage <= LIMIT else ORANGE, 28))
            box.add_widget(c)
        box.add_widget(self.label('نمودار متنی مصرف (هر ▉ حدود ۱۰ لیتر)', 14, PRIMARY, 38, True))
        for date, usage, *_ in reversed(rows):
            bars = '▉' * min(30, int(usage/10))
            box.add_widget(self.label(f'{date[5:]}  {bars}  {usage:.0f}', 12, GREEN if usage <= LIMIT else ORANGE, 30))
        return scroll


def sp(value):
    return dp(value)

if __name__ == '__main__':
    WaterSaver().run()
