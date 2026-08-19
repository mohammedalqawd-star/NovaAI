import asyncio, ast, logging, operator as op, os, re, sqlite3, math
from datetime import datetime
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

BOT_TOKEN=os.environ.get('BOT_TOKEN') or ''
OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY') or ''
MODEL=os.environ.get('OPENAI_MODEL') or 'gpt-5-mini'
ADMIN_ID=int(os.environ.get('ADMIN_ID') or '0')
DB_PATH=os.environ.get('DB_PATH') or 'novaai.db'
if not BOT_TOKEN: raise RuntimeError('BOT_TOKEN is missing')
logging.basicConfig(level=logging.INFO); bot=Bot(BOT_TOKEN); dp=Dispatcher()

def db():
 c=sqlite3.connect(DB_PATH); c.execute('CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,name TEXT,messages_left INTEGER DEFAULT 50,created_at TEXT)'); c.execute('CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,role TEXT,content TEXT,created_at TEXT)'); c.commit(); return c

def ensure_user(m):
 c=db(); u=m.from_user
 try:c.execute('ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0')
 except sqlite3.OperationalError:pass
 c.execute('INSERT OR IGNORE INTO users(user_id,username,name,messages_left,created_at,banned) VALUES(?,?,?,?,?,0)',(u.id,u.username,u.full_name,50,datetime.utcnow().isoformat())); c.execute('UPDATE users SET username=?,name=? WHERE user_id=?',(u.username,u.full_name,u.id)); c.commit(); n=c.execute('SELECT messages_left FROM users WHERE user_id=?',(u.id,)).fetchone()[0]; c.close(); return n

def balance(uid):
 c=db(); r=c.execute('SELECT messages_left FROM users WHERE user_id=?',(uid,)).fetchone(); c.close(); return r[0] if r else 0

def consume(uid):
 c=db(); c.execute('UPDATE users SET messages_left=messages_left-1 WHERE user_id=? AND messages_left>0',(uid,)); c.commit(); c.close()
def save(uid,role,text):
 c=db(); c.execute('INSERT INTO chats(user_id,role,content,created_at) VALUES(?,?,?,?)',(uid,role,text,datetime.utcnow().isoformat())); c.commit(); c.close()
def history(uid):
 c=db(); r=c.execute('SELECT role,content FROM chats WHERE user_id=? ORDER BY id DESC LIMIT 12',(uid,)).fetchall(); c.close(); return list(reversed(r))
def banned(uid):
 c=db(); r=c.execute('SELECT banned FROM users WHERE user_id=?',(uid,)).fetchone(); c.close(); return bool(r and r[0])

BIN={ast.Add:op.add,ast.Sub:op.sub,ast.Mult:op.mul,ast.Div:op.truediv,ast.FloorDiv:op.floordiv,ast.Pow:op.pow,ast.Mod:op.mod}; UN={ast.USub:op.neg,ast.UAdd:op.pos}
def calc(expr):
 expr=expr.replace('^','**').replace('×','*').replace('÷','/')
 if len(expr)>120 or not re.fullmatch(r'[0-9+\-*/().%\s]+',expr):raise ValueError()
 def w(n):
  if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and not isinstance(n.value,bool):return n.value
  if isinstance(n,ast.BinOp) and type(n.op) in BIN:
   a,b=w(n.left),w(n.right)
   if isinstance(n.op,ast.Pow) and abs(b)>10:raise ValueError()
   v=BIN[type(n.op)](a,b)
   if not math.isfinite(v) or abs(v)>10**15:raise ValueError()
   return v
  if isinstance(n,ast.UnaryOp) and type(n.op) in UN:return UN[type(n.op)](w(n.operand))
  raise ValueError()
 return w(ast.parse(expr,mode='eval').body)
def fmt(v):return str(int(v)) if isinstance(v,float) and v.is_integer() else (f'{v:.10g}' if isinstance(v,float) else str(v))
def extract_calc(t):
 for p in ('احسب','حاسبة','حساب','calculate','calc'):
  if t.lower().startswith(p.lower()):
   x=t[len(p):].strip(' :：');return x or None
 if re.fullmatch(r'[0-9+\-*/().%^×÷\s]+',t) and any(ch.isdigit() for ch in t):return t
 return None

def writing(t):
 req=re.sub(r'^(اكتب|اكتب لي|اكتبلي|صياغة|صغ|حسن|حسّن|write|draft)\s*','',t,flags=re.I).strip();l=req.lower()
 if any(k in l for k in ('إعلان','اعلان','تسويق','محل','متجر')):return f'📣 إعلان احترافي\n\n🔥 {req or "محلات القعود"}\n\nجودة مضمونة، خدمة ممتازة وأسعار مناسبة.\nنوفر لكم ما تحتاجونه بكل ثقة واهتمام.\n\n📍 زورونا اليوم\n📞 تواصلوا معنا لمعرفة التفاصيل\n\n⭐ محلات القعود — ثقة وجودة في كل تعامل'
 if 'تهنئة' in l or 'مبارك' in l:return '🎉 تهنئة جميلة\n\nألف مبارك! نسأل الله لكم دوام الفرح والنجاح والتوفيق. 🌷'
 if 'رسالة' in l or 'واتساب' in l:return '💬 رسالة جاهزة:\n\nالسلام عليكم، نرحب بكم ونسعد بخدمتكم. لأي استفسار أو طلب، تواصلوا معنا وسنكون سعيدين بمساعدتكم. 🌟'
 if 'سيرة' in l or 'cv' in l:return '📄 قالب سيرة ذاتية:\n\nالاسم:\nرقم الهاتف:\nالبريد الإلكتروني:\nالمهارات:\nالخبرات:\nالتعليم:\nالهدف المهني:'
 return f'✍️ صياغة مجانية:\n\n{req or "اكتب إعلان لمحلات القعود"}\n\nأرسل نوع النص والهدف والجمهور للحصول على صياغة أدق.'

def free_tool(t):
 x=t.strip();l=x.lower();expr=extract_calc(x)
 if expr:
  try:return f'🧮 النتيجة: {fmt(calc(expr))}'
  except ZeroDivisionError:return '❌ لا يمكن القسمة على صفر.'
  except:return '❌ العملية غير صحيحة. مثال: احسب 250*4+100'
 if re.match(r'^(اكتب|اكتب لي|اكتبلي|صياغة|صغ|حسن|حسّن|write|draft)\b',x,re.I):return writing(x)
 m=re.match(r'^(?:عدد الكلمات|احسب الكلمات)\s*[:：]\s*(.*)$',x,re.I)
 if m:
  s=m.group(1);return f'🔢 الكلمات: {len(s.split())}\n🔤 الأحرف: {len(s)}\n📏 بدون مسافات: {len(re.sub(r"\s+", "", s))}'
 if l.startswith('اعكس'):
  s=x.split(':',1)[1].strip() if ':' in x else x[4:].strip();return f'🔄 النص المعكوس:\n{s[::-1]}'
 m=re.match(r'^كرر\s+(.+?)\s+(\d+)\s*$',x,re.S)
 if m:
  n=min(int(m.group(2)),20);return '\n'.join(f'{i+1}️⃣ {m.group(1)}' for i in range(n))
 m=re.match(r'^(?:نظف|نظّف|تنظيف)\s*[:：]?\s*(.*)$',x,re.S)
 if m:return f'🧹 النص المنظف:\n{re.sub(r"\s+"," ",m.group(1)).strip()}'
 m=re.match(r'^(?:زخرف|زخرفة)\s*[:：]?\s*(.*)$',x,re.S)
 if m:
  s=m.group(1).strip();return f'✨ زخرفة:\n『 {s} 』\n★ {s} ★\n• {s} •\n╰┈➤ {s}'
 m=re.match(r'^(?:كبير|uppercase)\s*[:：]?\s*(.*)$',x,re.S)
 if m:return f'🔠 {m.group(1).upper()}'
 m=re.match(r'^(?:صغير|lowercase)\s*[:：]?\s*(.*)$',x,re.S)
 if m:return f'🔡 {m.group(1).lower()}'
 if x in ('مرحبا','هلا','السلام عليكم') or l in ('hello','hi'):return '🤖 أهلاً بك! أنا NovaBiz AI، وجاهز لمساعدتك.'
 if any(k in x for k in ('كيف حالك','كيفك','كيف حالكم')):return 'بخير والحمد لله 🤖❤️ وجاهز لمساعدتك!'
 if 'من أنت' in x or 'من انت' in x:return '🤖 أنا NovaBiz AI وأعمل بأدوات مجانية محلية بدون API.'
 return None

async def ask_ai(uid,text):
 if OPENAI_API_KEY:
  payload={'model':MODEL,'input':[{'role':r,'content':c} for r,c in history(uid)]+[{'role':'user','content':text}],'instructions':'أنت NovaBiz AI، مساعد عربي مفيد وودود. أجب بالعربية عند استخدام العربية.'};headers={'Authorization':f'Bearer {OPENAI_API_KEY}','Content-Type':'application/json'}
  async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as s:
   async with s.post('https://api.openai.com/v1/responses',headers=headers,json=payload) as r:
    data=await r.json()
    if r.status>=400:raise RuntimeError(data.get('error',{}).get('message','AI error'))
    return data.get('output_text','لم أستطع توليد رد الآن.')
 return free_tool(text) or '🆓 الأدوات المجانية: اكتب «الأدوات» لرؤيتها.'

kb=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='🧠 الذكاء الاصطناعي'),KeyboardButton(text='💰 رصيدي')],[KeyboardButton(text='🧮 حاسبة'),KeyboardButton(text='✍️ كتابة')],[KeyboardButton(text='🔧 الأدوات المجانية'),KeyboardButton(text='👤 حسابي')],[KeyboardButton(text='ℹ️ المساعدة')]],resize_keyboard=True)
admin_kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📊 الإحصائيات',callback_data='adm_stats'),InlineKeyboardButton(text='👥 المستخدمون',callback_data='adm_users')],[InlineKeyboardButton(text='💰 إضافة رصيد',callback_data='adm_add'),InlineKeyboardButton(text='🚫 حظر مستخدم',callback_data='adm_ban')],[InlineKeyboardButton(text='📢 إذاعة',callback_data='adm_broadcast'),InlineKeyboardButton(text='🔄 تحديث',callback_data='adm_refresh')]])
def is_admin(m):return ADMIN_ID!=0 and m.from_user.id==ADMIN_ID

@dp.message(CommandStart())
async def start(m):ensure_user(m);await m.answer('🤖 أهلاً بك في *NovaBiz AI*\n\n🆓 أدوات مجانية تعمل بدون API.\n🎁 رصيدك: 50 رسالة\n\nأرسل طلبك أو اختر خدمة من القائمة.',parse_mode='Markdown',reply_markup=kb)
@dp.message(Command('balance'))
@dp.message(F.text=='💰 رصيدي')
async def bal(m):ensure_user(m);await m.answer(f'💰 رصيدك: *{balance(m.from_user.id)}* رسالة',parse_mode='Markdown')
@dp.message(F.text=='👤 حسابي')
async def profile(m):ensure_user(m);u=m.from_user;await m.answer(f'👤 حسابي\n\nID: `{u.id}`\nالاسم: {u.full_name}\nالرصيد: {balance(u.id)} رسالة',parse_mode='Markdown')
@dp.message(F.text=='🧮 حاسبة')
async def calc_help(m):await m.answer('🧮 اكتب: احسب 250*4+100')
@dp.message(F.text=='✍️ كتابة')
async def write_help(m):await m.answer('✍️ اكتب: اكتب إعلان لمحلات القعود')
@dp.message(F.text=='🔧 الأدوات المجانية')
async def tools(m):await m.answer('🔧 الأدوات المجانية:\n🧮 حاسبة\n✍️ كتابة\n🔢 عدد الكلمات: هذا نص\n🔄 اعكس: مرحبا\n🔁 كرر مرحبا 3\n🧹 نظف: هذا   نص\n✨ زخرف: NovaBiz AI\n🔠 كبير: hello\n🔡 صغير: HELLO')
@dp.message(Command('admin'))
async def admin(m):
 if not is_admin(m):return
 await m.answer('👑 *لوحة تحكم NovaBiz AI*\n\nاختر عملية:',parse_mode='Markdown',reply_markup=admin_kb)
@dp.callback_query(F.data=='adm_stats')
async def adm_stats(q):
 if q.from_user.id!=ADMIN_ID:return await q.answer('غير مصرح',show_alert=True)
 c=db();u=c.execute('SELECT COUNT(*) FROM users').fetchone()[0];ch=c.execute('SELECT COUNT(*) FROM chats').fetchone()[0];b=c.execute('SELECT COUNT(*) FROM users WHERE banned=1').fetchone()[0] if 'banned' in [x[1] for x in c.execute('PRAGMA table_info(users)')] else 0;c.close();await q.message.answer(f'📊 الإحصائيات\n👥 المستخدمون: {u}\n💬 الرسائل: {ch}\n🚫 المحظورون: {b}');await q.answer()
@dp.callback_query(F.data=='adm_users')
async def adm_users(q):
 if q.from_user.id!=ADMIN_ID:return await q.answer('غير مصرح',show_alert=True)
 c=db();rows=c.execute('SELECT user_id,name,messages_left FROM users ORDER BY rowid DESC LIMIT 15').fetchall();c.close();await q.message.answer('👥 آخر المستخدمين:\n\n'+('\n'.join(f'• {r[1] or "بدون اسم"} | `{r[0]}` | رصيد {r[2]}' for r in rows) or 'لا يوجد'),parse_mode='Markdown');await q.answer()
@dp.callback_query(F.data=='adm_add')
async def adm_add(q):
 if q.from_user.id==ADMIN_ID:await q.message.answer('💰 إضافة رصيد: /add ID عدد\nمثال: /add 123456789 25')
 await q.answer()
@dp.callback_query(F.data=='adm_ban')
async def adm_ban(q):
 if q.from_user.id==ADMIN_ID:await q.message.answer('🚫 حظر: /ban ID\nفك الحظر: /unban ID')
 await q.answer()
@dp.callback_query(F.data=='adm_broadcast')
async def adm_broadcast(q):
 if q.from_user.id==ADMIN_ID:await q.message.answer('📢 الإذاعة: /broadcast نص الرسالة')
 await q.answer()
@dp.callback_query(F.data=='adm_refresh')
async def adm_refresh(q):
 if q.from_user.id==ADMIN_ID:await q.message.edit_text('👑 *لوحة تحكم NovaBiz AI*\n\nاختر عملية:',parse_mode='Markdown',reply_markup=admin_kb)
 await q.answer()
@dp.message(Command('add'))
async def add(m):
 if not is_admin(m):return
 p=m.text.split()
 if len(p)!=3 or not p[1].isdigit() or not p[2].lstrip('-').isdigit():return await m.answer('الاستخدام: /add ID عدد')
 c=db();c.execute('UPDATE users SET messages_left=messages_left+? WHERE user_id=?',(int(p[2]),int(p[1])));c.commit();c.close();await m.answer('✅ تم تحديث الرصيد.')
@dp.message(Command('ban'))
async def ban(m):
 if not is_admin(m):return
 p=m.text.split()
 if len(p)==2 and p[1].isdigit():
  c=db();c.execute('UPDATE users SET banned=1 WHERE user_id=?',(int(p[1]),));c.commit();c.close();await m.answer('🚫 تم الحظر.')
@dp.message(Command('unban'))
async def unban(m):
 if not is_admin(m):return
 p=m.text.split()
 if len(p)==2 and p[1].isdigit():
  c=db();c.execute('UPDATE users SET banned=0 WHERE user_id=?',(int(p[1]),));c.commit();c.close();await m.answer('✅ تم فك الحظر.')
@dp.message(Command('broadcast'))
async def broadcast(m):
 if not is_admin(m):return
 text=m.text.partition(' ')[2].strip()
 if not text:return await m.answer('الاستخدام: /broadcast نص الرسالة')
 c=db();ids=[r[0] for r in c.execute('SELECT user_id FROM users').fetchall()];c.close();ok=fail=0
 for uid in ids:
  try:await bot.send_message(uid,text);ok+=1
  except Exception:fail+=1
 await m.answer(f'📢 تمت الإذاعة\n✅ {ok}\n❌ {fail}')
@dp.message(Command('stats'))
async def stats(m):
 if is_admin(m):await m.answer('استخدم /admin لفتح لوحة التحكم.')
@dp.message(Command('help'))
@dp.message(F.text=='ℹ️ المساعدة')
async def help_(m):await m.answer('🆓 NovaBiz AI\n\n🧠 ذكاء اصطناعي\n🧮 حاسبة\n✍️ كتابة\n🔧 أدوات مجانية\n💰 الرصيد\n👤 الحساب\n\nللمدير: /admin')
@dp.message(F.text=='🧠 الذكاء الاصطناعي')
async def ai_btn(m):await m.answer('🧠 اكتب سؤالك الآن.')
@dp.message(F.text)
async def chat(m):
 ensure_user(m)
 if banned(m.from_user.id):await m.answer('🚫 تم إيقاف حسابك.');return
 if balance(m.from_user.id)<=0:await m.answer('❌ انتهى رصيدك المجاني.');return
 await m.bot.send_chat_action(m.chat.id,'typing')
 try:
  ans=await ask_ai(m.from_user.id,m.text);save(m.from_user.id,'user',m.text);save(m.from_user.id,'assistant',ans);consume(m.from_user.id);await m.answer(ans)
 except Exception:logging.exception('chat error');await m.answer('⚠️ حدث خطأ مؤقت. حاول مرة أخرى.')

async def main():db().close();await dp.start_polling(bot)
if __name__=='__main__':asyncio.run(main())
