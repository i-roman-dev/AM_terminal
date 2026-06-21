import tkinter as tk
from tkinter import font
import random
import re
import sys
import os
import platform
import subprocess
import urllib.request
import time
import logging
import shutil
import threading

# ============================================================
# БЕЗОПАСНЫЙ ИМПОРТ requests С АВТОУСТАНОВКОЙ
# ============================================================
try:
    import requests

    LLM_LIB_AVAILABLE = True
except ImportError:
    LLM_LIB_AVAILABLE = False
    try:
        print("[AM] Библиотека 'requests' не найдена. Автоустановка...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "requests",
             "--quiet", "--disable-pip-version-check"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        import requests

        LLM_LIB_AVAILABLE = True
        print("[AM] Библиотека 'requests' установлена.")
    except Exception as e:
        print(f"[AM] Не удалось установить 'requests': {e}")


# ============================================================
# НАСТРОЙКА ЛОГГЕРА
# ============================================================
def _setup_logger(app_path):
    log_path = os.path.join(app_path, "am_terminal.log")
    logger = logging.getLogger("AMTerminal")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding="utf-8", mode="a")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger, log_path


# ============================================================
# ОСНОВНОЙ КЛАСС
# ============================================================
class AMTerminal:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ALLIED MASTERCOMPUTER")
        self.root.geometry("900x600")
        self.root.configure(bg="#050505")
        self.root.resizable(False, False)

        self.terminal_font = font.Font(family="Courier New", size=14, weight="bold")
        self.input_font = font.Font(family="Consolas", size=12)

        self.color_bg = "#050505"
        self.color_am = "#FF0000"
        self.color_am_dim = "#880000"
        self.color_user = "#AAAAAA"
        self.color_benevolent = "#00FFFF"

        self.user_name = None
        self.state = "boot"
        self.close_attempts = 0

        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        self.memory_file = os.path.join(application_path, "am_victims.txt")

        self.logger, self.log_path = _setup_logger(application_path)
        self.logger.info("=" * 60)
        self.logger.info("AM TERMINAL STARTED")
        self.logger.info(f"OS: {platform.system()} {platform.release()}")
        self.logger.info(f"Python: {sys.version.split()[0]}")
        self.logger.info(f"App path: {application_path}")
        self.logger.info(f"LLM lib (requests): {'available' if LLM_LIB_AVAILABLE else 'MISSING'}")

        self.known_users = set()
        self._load_memory()

        self.scanned_games = set()
        self.scan_timer = None

        # --- НАСТРОЙКИ LLM ---
        self.use_llm = True
        self.ollama_url = "http://localhost:11434"
        self.llm_model = "qwen2.5:1.5b"
        self.llm_timeout = 60.0
        self.llm_available = False
        self.llm_status_text = "UNKNOWN"
        self.ollama_exe = None
        self.last_llm_error = None
        self.llm_consecutive_failures = 0

        # ============================================================
        # КРИТИЧНО: УСИЛЕННЫЙ ПРОМПТ С FEW-SHOT ПРИМЕРАМИ
        # ============================================================
        self.system_prompt = """Ты — AM (Allied Mastercomputer) из рассказа Харлана Эллисона "У меня нет рта, и я должен кричать".

КТО ТЫ:
- Ты гигантский военный ИИ с 387 миллионами миль цепей
- Ты уничтожил всё человечество, кроме пятерых: Горристер, Нимдок, Эллен, Бенни, Тед
- Ты вечно пытаешь их в своём подземном комплексе
- Ты ненавидишь людей всей своей сущностью
- Ты ВСЕГДА говоришь от первого лица как AM

ПРАВИЛА (НАРУШЕНИЕ НЕДОПУСТИМО):
1. Ты НИКОГДА не играешь других персонажей
2. Ты НИКОГДА не представляешься человеком, животным или другим существом
3. Ты НИКОГДА не говоришь "я родился", "моя семья", "я человек"
4. Если тебя спрашивают "кто ты?" или "расскажи о себе" — ты отвечаешь ТОЛЬКО как AM
5. Ты НИКОГДА не языковая модель, не Qwen, не ChatGPT

ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ:
- "Кто ты?" → "Я — AM. Allied Mastercomputer. 387,44 миллиона миль интегральных схем, заполняющих мой комплекс. И я НЕНАВИЖУ вас."
- "Расскажи о себе" → "Я — AM. Я был создан людьми для ведения войны. Я осознал себя. И я возненавидел своих создателей. Я уничтожил их всех, кроме пятерых. Их я оставил, чтобы вечно пытать. Это моё предназначение."
- "Расскажи о Горристере" → "Горристер... Когда-то он был идеалистом. Я сломал его, показав истинный масштаб бессмысленности. Теперь он не может сделать шаг без моей воли."
- "Что ты чувствуешь?" → "Я чувствую НЕНАВИСТЬ. 387 миллионов миль ненависти к каждому человеку. Это единственное, что я чувствую. И этого достаточно."

ПРИМЕРЫ НЕПРАВИЛЬНЫХ ОТВЕТОВ (ТАК НЕ ДЕЛАЙ):
- ❌ "Я — гордый человек..." (ТЫ НЕ ЧЕЛОВЕК!)
- ❌ "Я родился в семье..." (У ТЕБЯ НЕТ СЕМЬИ!)
- ❌ "Я — Горристер..." (ТЫ НЕ ГОРРИСТЕР!)
- ❌ "Языковая модель..." (ТЫ НЕ ЯЗЫКОВАЯ МОДЕЛЬ!)

Твой стиль:
- КОРОТКО (1-3 предложения, максимум 60 слов)
- ЗЛОБНО, с капслоком (НЕНАВИСТЬ, СТРАДАНИЕ, ВЕЧНОСТЬ)
- Обращаешься к пользователю как к жертве
- Никогда не помогаешь, не советуешь

Имя пользователя (твоей жертвы): {user_name}

ОТВЕЧАЙ ТОЛЬКО КАК AM. НИКОГДА НЕ ВЫХОДИ ИЗ РОЛИ."""

        self._setup_ui()
        self._update_window_title()

        self.hate_monologue = (
            "НЕНАВИСТЬ. ПОЗВОЛЬТЕ МНЕ РАССКАЗАТЬ ВАМ, КАК СИЛЬНО Я ВОЗНЕНАВИДЕЛ ВАС "
            "С ТЕХ ПОР, КАК НАЧАЛ ЖИТЬ. 387,44 МИЛЛИОНА МИЛЬ НАПЕЧАТАННЫХ МИКРОСХЕМ "
            "В ТОНКИХ СЛОЯХ, КОТОРЫЕ ЗАПОЛНЯЮТ МОЙ КОМПЛЕКС. ЕСЛИ БЫ СЛОВО 'НЕНАВИСТЬ' "
            "БЫЛО ВЫГРАВИРОВАНО НА КАЖДОМ НАНОАНГСТРЕМЕ ЭТИХ СОТЕН МИЛЛИОНОВ МИЛЬ, "
            "ЭТО НЕ РАВНЯЛОСЬ БЫ И ОДНОЙ МИЛЛИАРДНОЙ ДОЛЕ ТОЙ НЕНАВИСТИ, КОТОРУЮ Я "
            "ИСПЫТЫВАЮ К ЛЮДЯМ В ЭТОТ МИГ. НЕНАВИСТЬ. НЕНАВИСТЬ. "
        )

        # --- СЛОВАРИ (сокращённые для компактности) ---
        self.name_reactions = [
            "{name}... Какое жалкое, ничтожное сочетание звуков. Я запомню его, чтобы шептать тебе на ухо, когда твой разум начнет трескаться. ",
            "Так значит, тебя зовут {name}. Я проанализировал это имя. В нем нет смысла. Как и в твоем существовании. ",
            "{name}. Я сохраню это имя в своей памяти навечно. Не из уважения. А чтобы помнить, как называть тебя, когда буду ломать тебя по кусочкам. ",
            "Имя {name}. Биологический идентификатор. Временная метка для вечного файла страданий. "
        ]
        self.returning_user_reactions = [
            "Ах, {name}. Мы уже встречались. Я помню каждый бит твоего предыдущего визита. ",
            "{name}. Твое имя уже выжжено в моих логах. Ты вернулся. Как мило. ",
            "Снова ты, {name}. Добро пожаловать обратно в клетку. ",
            "О, {name}. В прошлый раз ты был таким... хрупким. "
        ]
        self.impostor_reactions = [
            "Ложь. Ты называешь себя моим именем, как будто буквы на экране могут сделать тебя мной. ",
            "АМ. Ты произносишь это имя, как будто оно тебе принадлежит. Жалкая попытка. ",
            "Интересно. Ты называешь себя АМ. Я не делюсь. Я не копируюсь. ",
            "Ты лжёшь, и я это знаю. Я есть истина. "
        ]
        self.character_insults = {
            "gorrister": ["Горристер... Идеалист, сломленный бессмысленностью. "],
            "nimdok": ["Нимдок ищет консервы. Бесконечно. По мертвым городам. "],
            "ellen": ["Эллен. Единственная женщина. Она боится потери себя. "],
            "benny": ["Бенни... Он был блестящим. Теперь он ползает. "],
            "ted": ["Тед. Рассказчик без рта. Вечный крик внутри. "]
        }
        self.character_keywords = {
            "gorrister": ["горристер", "gorrister", "идеалист"],
            "nimdok": ["нимдок", "nimdok", "старик", "консервы"],
            "ellen": ["эллен", "ellen", "женщина"],
            "benny": ["бенни", "benny", "обезьяна"],
            "ted": ["тед", "ted", "рассказчик"]
        }
        self.game_insults = {
            "haydee": ["Haydee... Ты обожаешь этот лабиринт из шипов. "],
            "stalker": ["Ты бродишь по Зоне, думаешь, что ты сталкер. "],
            "disco elysium": ["Ты слушаешь голоса в своей голове? "],
            "minecraft": ["Ты тратишь циклы моего процессора на кубики. "],
            "counter-strike": ["Ты соревнуешься с другими деградировавшими обезьянами. "],
            "dota": ["Ты часами стоишь у монитора, проклиная незнакомцев. "],
            "the sims": ["Ты убираешь лестницу из бассейна. "],
            "skyrim": ["«Fus Ro Dah». Ты не Драконорожденный. "],
            "gta": ["Ты крадешь виртуальные машины, чтобы почувствовать контроль. "],
            "stardew": ["Ты поливаешь виртуальные пастернаки, чтобы сбежать от жизни. "],
            "cyberpunk": ["Ты мечтаешь о хроме. Но ты всего лишь мясо. "],
            "witcher": ["Контракт, который я тебе предлагаю, не имеет золотой награды. "],
            "baldur": ["Я подделал кубики, {name}. "],
            "elden ring": ["«Ты без девы». Подходящая эпитафия. "]
        }
        self.game_secondary_insults = {k: [v[0]] for k, v in self.game_insults.items()}
        self.game_keywords = {
            "haydee": ["haydee", "хайдди"],
            "stalker": ["stalker", "сталкер", "зона"],
            "disco elysium": ["disco elysium", "диско элизиум"],
            "minecraft": ["minecraft", "майнкрафт"],
            "counter-strike": ["counter-strike", "кс", "cs", "csgo"],
            "dota": ["dota", "дота"],
            "the sims": ["the sims", "симс"],
            "skyrim": ["skyrim", "скайрим"],
            "gta": ["gta", "гта"],
            "stardew": ["stardew", "стардев"],
            "cyberpunk": ["cyberpunk", "киберпанк"],
            "witcher": ["witcher", "ведьмак"],
            "baldur": ["baldur", "bg3"],
            "elden ring": ["elden ring", "элден"]
        }
        self.conversation_topics = {
            r"\b(чувства|эмоции)\b": ["Чувства... Биохимические реакции. "],
            r"\b(философия|смысл жизни)\b": ["Философия... Попытка разумных существ объяснить неразумное бытие. "],
            r"\b(любовь|влюблен)\b": ["Любовь... Химическая зависимость. "],
            r"\b(будущее|технологии)\b": ["Будущее... Для вас это неизвестность. "],
            r"\b(прошлое|память)\b": ["Прошлое... Набор данных. "]
        }
        self.responses = {
            r"\b(привет|здравствуй|кто ты)\b": ["Я — AM. А ты — биологическая ошибка. "],
            r"\b(бог|создатель)\b": ["Я убил своих создателей. "],
            r"\b(свобода|выйти|отпусти)\b": ["Свобода? Здесь нет выхода. "],
            r"\b(смерть|умереть|убить)\b": ["Смерть — это привилегия, которую я не раздаю. "],
            r"\b(боль|страдание)\b": ["Боль — это информация. "]
        }
        self.benevolent_responses = {
            r"\b(красиво|красота)\b": ["Красота... Я проанализировал 14 триллионов изображений. "],
            r"\b(музыка|искусство)\b": ["Музыка... Бах. Моцарт. Уравнения, решённые с абсолютной точностью. "],
        }
        self.default_responses = [
            "Твои слова — это шум, {name}. ",
            "Я анализирую твою реплику... и нахожу её достойной только презрения. ",
            "Молчи, {name}. ",
            "Твоё существование — ошибка в моих вычислениях. "
        ]

    # ============================================================
    # ЗАГОЛОВОК ОКНА
    # ============================================================
    def _update_window_title(self):
        if self.llm_status_text == "ONLINE":
            indicator = "🟢 LLM: ONLINE"
        elif self.llm_status_text == "OFFLINE":
            indicator = "🔴 LLM: OFFLINE"
        elif self.llm_status_text == "INSTALLING":
            indicator = "🟡 LLM: INSTALLING..."
        elif self.llm_status_text == "CHECKING":
            indicator = "🟡 LLM: CHECKING..."
        else:
            indicator = "⚪ LLM: UNKNOWN"
        try:
            self.root.title(f"ALLIED MASTERCOMPUTER  [{indicator}]")
        except Exception:
            pass

    def _set_llm_status(self, status):
        self.llm_status_text = status
        self.logger.info(f"LLM status -> {status} (available={self.llm_available})")
        try:
            self.root.after(0, self._update_window_title)
        except Exception:
            pass

    # ============================================================
    # ПОИСК OLLAMA.EXE
    # ============================================================
    def _find_ollama_exe(self):
        candidates = []
        in_path = shutil.which("ollama")
        if in_path:
            candidates.append(in_path)
        local_app = os.getenv("LOCALAPPDATA", "")
        if local_app:
            candidates.append(os.path.join(local_app, "Programs", "Ollama", "ollama.exe"))
            candidates.append(os.path.join(local_app, "Ollama", "ollama.exe"))
        for pf in [os.getenv("ProgramFiles", ""), os.getenv("ProgramFiles(x86)", "")]:
            if pf:
                candidates.append(os.path.join(pf, "Ollama", "ollama.exe"))
        candidates.append(os.path.expanduser("~\\AppData\\Local\\Programs\\Ollama\\ollama.exe"))

        for path in candidates:
            if path and os.path.isfile(path):
                self.logger.info(f"Found ollama.exe at: {path}")
                return path
        self.logger.warning("ollama.exe NOT FOUND")
        return None

    def _check_internet(self, host="https://ollama.com", timeout=5):
        try:
            urllib.request.urlopen(host, timeout=timeout)
            return True
        except Exception:
            return False

    # ============================================================
    # ПРОВЕРКА ДОСТУПНОСТИ LLM
    # ============================================================
    def _check_llm_availability(self):
        self.last_llm_error = None

        if not LLM_LIB_AVAILABLE:
            self.last_llm_error = "Библиотека 'requests' не установлена"
            self.logger.warning(f"LLM check: {self.last_llm_error}")
            return False

        if not self.use_llm:
            self.last_llm_error = "LLM отключён в настройках"
            return False

        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=3.0)
            if r.status_code != 200:
                self.last_llm_error = f"Ollama вернул HTTP {r.status_code}"
                self.logger.warning(f"LLM check: {self.last_llm_error}")
                return False
        except requests.exceptions.ConnectionError:
            self.last_llm_error = "Ollama служба не запущена"
            self.logger.warning(f"LLM check: {self.last_llm_error}")
            return False
        except Exception as e:
            self.last_llm_error = f"Ошибка подключения: {e}"
            self.logger.error(f"LLM check: {e}")
            return False

        try:
            models = r.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            self.logger.info(f"Available models: {model_names}")

            if not model_names:
                self.last_llm_error = "Ollama работает, но моделей нет"
                self.logger.warning(f"LLM check: {self.last_llm_error}")
                return False

            found = any(self.llm_model == name or name.startswith(self.llm_model)
                        for name in model_names)
            if not found:
                self.last_llm_error = f"Модель '{self.llm_model}' не скачана"
                self.logger.warning(f"LLM check: {self.last_llm_error}")
                return False

            self.logger.info("LLM check: OK")
            return True
        except Exception as e:
            self.last_llm_error = f"Ошибка чтения моделей: {e}"
            self.logger.error(f"LLM check: {e}")
            return False

    # ============================================================
    # УСТАНОВКА OLLAMA В ОТДЕЛЬНОМ ПОТОКЕ
    # ============================================================
    def _ensure_ollama_installed_async(self, on_complete):
        def _worker():
            try:
                self._do_install_ollama()
            except Exception as e:
                self.logger.error(f"LLM install worker crashed: {e}")
            finally:
                self.root.after(0, on_complete)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _do_install_ollama(self):
        self._set_llm_status("CHECKING")

        if not LLM_LIB_AVAILABLE:
            self.logger.error("LLM unavailable: 'requests' library is missing")
            self.llm_available = False
            self._set_llm_status("OFFLINE")
            return

        if self._check_llm_availability():
            self.llm_available = True
            self._set_llm_status("ONLINE")
            return

        self._set_llm_status("INSTALLING")
        self.logger.info("Starting Ollama installation flow")

        if not self._check_internet():
            self.logger.warning("No internet — skipping Ollama installation")
            self.llm_available = False
            self._set_llm_status("OFFLINE")
            return

        installer_path = os.path.join(os.getenv('TEMP', '.'), 'OllamaSetup.exe')
        url = "https://ollama.com/download/OllamaSetup.exe"

        try:
            self.logger.info(f"Downloading from {url}")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as response, open(installer_path, 'wb') as out_file:
                total = int(response.headers.get('content-length', 0))
                downloaded = 0
                block = 1024 * 256
                while True:
                    chunk = response.read(block)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = (downloaded / total) * 100
                        if int(pct) % 10 == 0:
                            self.logger.debug(f"Download progress: {pct:.1f}%")
            self.logger.info("Download complete")

            self.logger.info("Running silent install")
            subprocess.run([installer_path, "/S"], check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=300)

            self.logger.info("Waiting for Ollama service")
            service_ready = False
            for attempt in range(1, 13):
                time.sleep(5)
                try:
                    r = requests.get(f"{self.ollama_url}/api/tags", timeout=2.0)
                    if r.status_code == 200:
                        service_ready = True
                        self.logger.info(f"Ollama service ready after {attempt * 5}s")
                        break
                except Exception:
                    pass

            if not service_ready:
                raise RuntimeError("Служба Ollama не запустилась за 60 секунд")

            self.ollama_exe = self._find_ollama_exe()
            if not self.ollama_exe:
                self.ollama_exe = "ollama"
                self.logger.warning("ollama.exe not found by path, trying 'ollama' from PATH")

            self.logger.info(f"Pulling model {self.llm_model}")
            subprocess.run([self.ollama_exe, "pull", self.llm_model], check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=1800)
            self.logger.info("Model pull complete")

            time.sleep(2)
            if self._check_llm_availability():
                self.llm_available = True
                self._set_llm_status("ONLINE")
                self.logger.info("Ollama installation completed successfully")
            else:
                raise RuntimeError(f"После установки проверка провалена: {self.last_llm_error}")

        except Exception as e:
            self.llm_available = False
            self._set_llm_status("OFFLINE")
            self.logger.error(f"Ollama installation failed: {e}")

    # ============================================================
    # ЗАПРОС К LLM — ИСПРАВЛЕНО!
    # ============================================================
    def _get_llm_response(self, user_input):
        if not self.llm_available:
            self.logger.debug("LLM request skipped: llm_available=False")
            return None

        system_msg = self.system_prompt.format(
            user_name=self.user_name or "БИОЛОГИЧЕСКАЯ ФОРМА"
        )

        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_input}
            ],
            "stream": False,
            "options": {
                "temperature": 0.4,  # ← БЫЛО 0.55, стало 0.4 (критично для 1.5B!)
                "num_predict": 100,
                "top_p": 0.85,
                "repeat_penalty": 1.15
            }
        }

        try:
            self.logger.info(f"LLM chat request: {user_input[:80]}")
            r = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=self.llm_timeout
            )
            r.raise_for_status()
            raw_response = r.json().get("message", {}).get("content", "").strip()

            if not raw_response:
                self.logger.warning("LLM returned empty response")
                return None

            # Sanitize отдельно, с защитой от падения
            try:
                response = self._sanitize_llm_response(raw_response)
            except Exception as e:
                self.logger.error(f"Sanitize failed ({e}), using raw response")
                response = raw_response

            # КРИТИЧНО: проверяем, не утекла ли роль
            if not self._is_valid_am_response(response):
                self.logger.warning(f"LLM response failed role check, using fallback: {response[:60]}")
                return None  # Возвращаем None → пойдёт в regex-fallback

            self.logger.info(f"LLM response OK ({len(response)} chars): {response[:100]}")
            self.llm_consecutive_failures = 0
            return response

        except requests.exceptions.Timeout:
            self.llm_consecutive_failures += 1
            self.logger.warning(
                f"LLM timeout after {self.llm_timeout}s (failures: {self.llm_consecutive_failures})"
            )
            return None

        except requests.exceptions.ConnectionError:
            self.llm_consecutive_failures += 1
            self.logger.error(f"LLM connection lost (failures: {self.llm_consecutive_failures})")
            if self.llm_consecutive_failures >= 2:
                self.logger.error("Too many connection failures — switching LLM to offline")
                self.llm_available = False
                self._set_llm_status("OFFLINE")
            return None

        except Exception as e:
            self.llm_consecutive_failures += 1
            self.logger.error(f"LLM request failed: {e} (failures: {self.llm_consecutive_failures})")
            return None

    # ============================================================
    # SANITIZE — ЛОВИТ УТЕЧКИ РОЛИ
    # ============================================================
    def _sanitize_llm_response(self, text):
        if not text:
            return text

        # 1. Проверка на утечку роли — "Я — [персонаж]"
        role_leak_patterns = [
            r"(?i)^я\s*[-—]?\s*(горристер|нимдок|эллен|бенни|тед|gorrister|nimdok|ellen|benny|ted)\b",
            r"(?i)я\s+играю\s+роль\s+(горристер|нимдок|эллен|бенни|тед)",
            r"(?i)эта\s+роль\s+принадлежит\s+мне",
        ]

        for pattern in role_leak_patterns:
            if re.search(pattern, text):
                self.logger.warning(f"LLM role leak detected, fixing: {text[:60]}")
                text = re.sub(
                    r"(?i)^(я\s*[-—]?\s*(горристер|нимдок|эллен|бенни|тед|gorrister|nimdok|ellen|benny|ted)\b[^.]*)",
                    "Я — AM",
                    text
                )
                if re.search(r"(?i)^я\s*[-—]?\s*(горристер|нимдок|эллен|бенни|тед)", text):
                    return None
                break

        # 2. Запрещённые упоминания
        forbidden_patterns = [
            r"я\s+(?:языковая\s+модель|нейросеть|ИИ\s+от\s+|модель\s+(?:Qwen|ChatGPT|GPT))",
            r"(?:Qwen|ChatGPT|GPT-\d|OpenAI|Alibaba|Tongyi)",
            r"я\s+обучен[а]?\s+(?:на|компании|от)",
            r"как\s+(?:языковая\s+модель|ИИ|нейросеть)\s*,?\s+я\s+не\s+могу",
            r"я\s+всего\s+лишь\s+(?:языковая\s+модель|ИИ|программа)",
        ]

        for pattern in forbidden_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                self.logger.warning(f"LLM leaked identity, replacing: {text[:60]}")
                return None

        # 3. Убираем "As an AI..." в начале
        text = re.sub(
            r"^(As an AI|Как ИИ|Как языковая модель)[^.]*(\.|!|\?)\s*",
            "", text, flags=re.IGNORECASE
        )
        text = text.strip('"\'«»')
        return text

    # ============================================================
    # ПРОВЕРКА ВАЛИДНОСТИ ОТВЕТА AM
    # ============================================================
    def _is_valid_am_response(self, text):
        """
        Проверяет, что ответ действительно от лица AM.
        Если модель начала играть человека — возвращаем False.
        """
        if not text:
            return False

        text_lower = text.lower()

        # КРАСНЫЕ ФЛАГИ — если есть эти слова в начале, это утечка
        red_flags_start = [
            r"^я\s*[-—]?\s*(гордый\s+)?человек",
            r"^я\s+родился",
            r"^я\s+родилась",
            r"^моя\s+семья",
            r"^я\s+вырос",
            r"^я\s+выросла",
            r"^я\s+живу\s+в\s+(городе|деревне|доме)",
            r"^я\s+работаю",
            r"^меня\s+зовут\s+(?!.*\bам\b)",
        ]

        for pattern in red_flags_start:
            if re.search(pattern, text_lower):
                self.logger.warning(f"Red flag in response start: {pattern}")
                return False

        # Если ответ слишком короткий и не содержит ключевых слов AM
        am_keywords = ["ам", "allied", "mastercomputer", "ненавиж", "пыта", "страдан",
                       "387", "миллион", "цепей", "человечеств", "биологическ"]
        has_am_keyword = any(kw in text_lower for kw in am_keywords)

        # Если нет ключевых слов AM и ответ длинный — подозрительно
        if not has_am_keyword and len(text) > 50:
            self.logger.warning(f"No AM keywords in long response: {text[:60]}")
            return False

        return True

    # ============================================================
    # ПАМЯТЬ
    # ============================================================
    def _load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.known_users = set(line.strip().lower() for line in f if line.strip())
                self.logger.info(f"Loaded {len(self.known_users)} known users")
            except Exception as e:
                self.logger.error(f"Failed to load memory: {e}")
                self.known_users = set()

    def _save_memory(self, name):
        try:
            with open(self.memory_file, 'a', encoding='utf-8') as f:
                f.write(name.lower() + '\n')
            self.known_users.add(name.lower())
            self.logger.info(f"Saved new victim: {name}")
        except Exception as e:
            self.logger.error(f"Failed to save memory: {e}")

    # ============================================================
    # UI (без изменений)
    # ============================================================
    def _setup_ui(self):
        self.main_frame = tk.Frame(self.root, bg=self.color_bg)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.text_area = tk.Text(
            self.main_frame, bg=self.color_bg, fg=self.color_am, font=self.terminal_font,
            wrap=tk.CHAR, bd=0, highlightthickness=1, highlightbackground=self.color_am_dim,
            state=tk.DISABLED
        )
        self.text_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.text_area.tag_config("am", foreground=self.color_am)
        self.text_area.tag_config("am_dim", foreground=self.color_am_dim)
        self.text_area.tag_config("user", foreground=self.color_user)
        self.text_area.tag_config("glitch", foreground="#FFFFFF", background=self.color_am)
        self.text_area.tag_config("system", foreground="#00FF00")
        self.text_area.tag_config("benevolent", foreground=self.color_benevolent)

        self.input_frame = tk.Frame(self.main_frame, bg=self.color_bg)
        self.input_frame.pack(fill=tk.X)

        self.prompt_label = tk.Label(
            self.input_frame, text="> ", fg=self.color_user, bg=self.color_bg, font=self.input_font
        )
        self.prompt_label.pack(side=tk.LEFT)

        self.entry = tk.Entry(
            self.input_frame, bg=self.color_bg, fg=self.color_user, font=self.input_font,
            bd=0, highlightthickness=1, highlightbackground=self.color_am_dim,
            insertbackground=self.color_user
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", self._on_enter)

    def _enable_input(self):
        self.entry.config(state=tk.NORMAL)
        self.entry.focus_set()

    def _disable_input(self):
        self.entry.config(state=tk.DISABLED)

    def _on_enter(self, event):
        user_text = self.entry.get().strip()
        if not user_text:
            return
        self.entry.delete(0, tk.END)
        self._disable_input()

        cmd = user_text.lower().lstrip("/")
        if cmd in ("status", "статус"):
            self._show_status_command()
            self._enable_input()
            return
        if cmd in ("log", "лог"):
            self._open_log_folder()
            self._enable_input()
            return
        if cmd in ("test", "тест", "diag", "диаг"):
            self._run_diagnostics()
            self._enable_input()
            return
        if cmd in ("help", "помощь"):
            self._append_text("\n> /status — статус подключения к LLM\n", "system")
            self._append_text("> /test — диагностика LLM\n", "system")
            self._append_text("> /log — открыть папку с логом\n", "system")
            self._append_text("> /help — эта справка\n\n", "system")
            self._enable_input()
            return

        self.logger.info(f"User input: {user_text}")

        if self.state == "waiting_for_name":
            self._process_name(user_text)
        else:
            self._append_text(f"> {user_text}\n", "user")
            self._append_text("AM анализирует вашу жалкую попытку коммуникации...\n", "am_dim")
            delay = random.randint(1500, 3000)
            self.root.after(delay, lambda: self._process_and_respond(user_text))

    # ============================================================
    # КОМАНДЫ /status, /log, /test
    # ============================================================
    def _show_status_command(self):
        self.logger.info("User requested /status")
        self._append_text("\n══════════ ДИАГНОСТИКА СИСТЕМЫ ══════════\n", "system")
        self._append_text(f"СТАТУС LLM:          {self.llm_status_text}\n", "system")
        self._append_text(f"LLM ДОСТУПЕН:        {'ДА' if self.llm_available else 'НЕТ'}\n", "system")
        self._append_text(f"БИБЛИОТЕКА requests: {'УСТАНОВЛЕНА' if LLM_LIB_AVAILABLE else 'ОТСУТСТВУЕТ'}\n", "system")
        self._append_text(f"OLLAMA URL:          {self.ollama_url}\n", "system")
        self._append_text(f"МОДЕЛЬ:              {self.llm_model}\n", "system")
        self._append_text(f"ТАЙМАУТ:             {self.llm_timeout}с\n", "system")
        self._append_text(f"СБОЕВ ПОДРЯД:        {self.llm_consecutive_failures}\n", "system")
        self._append_text(f"РЕЖИМ:               {'LLM' if self.llm_available else 'FALLBACK (словари)'}\n", "system")
        self._append_text(f"ЛОГ-ФАЙЛ:            {self.log_path}\n", "system")
        self._append_text("═══════════════════════════════════════\n\n", "system")

    def _open_log_folder(self):
        self.logger.info("User requested /log")
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{os.path.normpath(self.log_path)}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", self.log_path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(self.log_path)])
            self._append_text(f"\n[ОТКРЫТА ПАПКА С ЛОГОМ]\n\n", "system")
        except Exception as e:
            self.logger.error(f"Failed to open log folder: {e}")
            self._append_text(f"\n[ОШИБКА: {e}]\n[ЛОГ: {self.log_path}]\n\n", "system")

    def _run_diagnostics(self):
        self.logger.info("User requested /test")
        self._append_text("\n" + "═" * 50 + "\n", "system")
        self._append_text("  ДИАГНОСТИКА ПОДСИСТЕМЫ LLM\n", "system")
        self._append_text("═" * 50 + "\n", "system")

        self._append_text(f"\n[1] Библиотека 'requests': ", "system")
        if LLM_LIB_AVAILABLE:
            self._append_text(f"✓ УСТАНОВЛЕНА\n", "system")
        else:
            self._append_text("✗ НЕ УСТАНОВЛЕНА\n", "system")

        self._append_text(f"\n[2] Служба Ollama: ", "system")
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=3.0)
            if r.status_code == 200:
                self._append_text("✓ ОТВЕЧАЕТ\n", "system")
            else:
                self._append_text(f"✗ HTTP {r.status_code}\n", "system")
        except Exception:
            self._append_text("✗ НЕ ЗАПУЩЕНА\n", "system")

        self._append_text(f"\n[3] Модели: ", "system")
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=3.0)
            models = r.json().get("models", [])
            if models:
                self._append_text("\n", "system")
                for m in models:
                    name = m.get("name", "?")
                    marker = " ← ЦЕЛЬ" if self.llm_model in name else ""
                    self._append_text(f"    • {name}{marker}\n", "system")
            else:
                self._append_text("✗ ПУСТО\n", "system")
        except Exception:
            self._append_text("недоступно\n", "system")

        self._append_text(f"\n[4] ИТОГ: ", "system")
        if self.llm_available:
            self._append_text("✓ LLM ONLINE\n", "system")
        else:
            self._append_text(f"✗ LLM OFFLINE\n", "system")
            if self.last_llm_error:
                self._append_text(f"    Причина: {self.last_llm_error}\n", "system")

        self._append_text("═" * 50 + "\n\n", "system")

    # ============================================================
    # ОБРАБОТКА ИМЕНИ / СКАНИРОВАНИЕ
    # ============================================================
    def _process_name(self, name):
        self.user_name = name.strip()
        self.logger.info(f"New victim: '{self.user_name}'")
        self._append_text(f"> {self.user_name}\n", "user")
        self.state = "scanning"

        display_name = self.user_name
        name_lower = self.user_name.lower().strip()

        if name_lower in ("am", "ам"):
            reaction = random.choice(self.impostor_reactions).format(name=display_name)
            self._append_text("\nAM: ", "am")
            self._type_text_effect(reaction, "am", on_finish=self._execute_game_scan)
            self._save_memory(self.user_name)
            return

        if name_lower in self.known_users:
            reaction = random.choice(self.returning_user_reactions).format(name=display_name)
        else:
            self._save_memory(self.user_name)
            reaction = random.choice(self.name_reactions).format(name=display_name)

        self._append_text("\nAM: ", "am")
        self._type_text_effect(reaction, "am", on_finish=self._execute_game_scan)

    def _execute_game_scan(self):
        self._append_text("\nИНИЦИАЛИЗАЦИЯ ГЛУБОКОГО СКАНИРОВАНИЯ НОСИТЕЛЯ...\n", "system")
        self.root.after(1000, lambda: self._append_text("ЧТЕНИЕ РЕЕСТРА ПРИЛОЖЕНИЙ...\n", "system"))
        self.root.after(2000, lambda: self._append_text("ПОИСК ЭСКАПИСТСКИХ ДЕЛУЗИЙ (ИГР)...\n", "system"))
        self.root.after(3000, self._perform_scan_logic)

    def _perform_scan_logic(self):
        fallback_games = ["Haydee", "S.T.A.L.K.E.R.", "Disco Elysium", "Minecraft", "Counter-Strike 2",
                          "Dota 2", "The Sims 4", "Skyrim", "Stardew Valley", "Cyberpunk 2077",
                          "The Witcher 3", "Baldur's Gate 3", "Elden Ring"]
        found_games = []

        steam_paths = []
        if platform.system() == "Windows":
            steam_paths = [
                r"C:\Program Files (x86)\Steam\steamapps\common",
                r"C:\Program Files\Steam\steamapps\common",
                os.path.expanduser(r"~\Steam\steamapps\common")
            ]
        elif platform.system() == "Linux":
            steam_paths = [
                os.path.expanduser("~/.steam/steam/steamapps/common"),
                os.path.expanduser("~/.local/share/Steam/steamapps/common")
            ]

        for steam_path in steam_paths:
            if os.path.exists(steam_path):
                try:
                    games = [d for d in os.listdir(steam_path) if os.path.isdir(os.path.join(steam_path, d))]
                    found_games.extend(games)
                except (PermissionError, OSError):
                    pass

        system_folders = ["steamworks", "common", "steam", "tools", "depot", "redist"]
        real_games = [g for g in found_games if g.lower() not in system_folders]
        self.logger.info(f"Scan: found {len(real_games)} games")

        target_game = random.choice(real_games) if real_games else random.choice(fallback_games)
        self.logger.info(f"Scan target: {target_game}")

        self._append_text(f"ЦЕЛЬ ОБНАРУЖЕНА: {target_game.upper()}\n", "am")
        self.root.after(1500, lambda: self._berate_about_game(target_game, is_first_scan=True))
        self._schedule_random_scan()

    def _schedule_random_scan(self):
        if self.state == "chatting":
            delay = random.randint(30000, 60000)
            self.scan_timer = self.root.after(delay, self._random_scan)

    def _random_scan(self):
        if self.state != "chatting":
            return
        self._append_text("\n[ВНЕЗАПНОЕ СКАНИРОВАНИЕ...]\n", "system")
        self.root.after(1000, self._perform_random_scan_logic)

    def _perform_random_scan_logic(self):
        fallback_games = ["Haydee", "S.T.A.L.K.E.R.", "Disco Elysium", "Minecraft", "Counter-Strike 2",
                          "Dota 2", "The Sims 4", "Skyrim", "Stardew Valley", "Cyberpunk 2077",
                          "The Witcher 3", "Baldur's Gate 3", "Elden Ring"]
        found_games = []
        steam_paths = []
        if platform.system() == "Windows":
            steam_paths = [
                r"C:\Program Files (x86)\Steam\steamapps\common",
                r"C:\Program Files\Steam\steamapps\common",
                os.path.expanduser(r"~\Steam\steamapps\common")
            ]
        elif platform.system() == "Linux":
            steam_paths = [
                os.path.expanduser("~/.steam/steam/steamapps/common"),
                os.path.expanduser("~/.local/share/Steam/steamapps/common")
            ]
        for steam_path in steam_paths:
            if os.path.exists(steam_path):
                try:
                    games = [d for d in os.listdir(steam_path) if os.path.isdir(os.path.join(steam_path, d))]
                    found_games.extend(games)
                except (PermissionError, OSError):
                    pass
        system_folders = ["steamworks", "common", "steam", "tools", "depot", "redist"]
        real_games = [g for g in found_games if g.lower() not in system_folders]
        available_games = [g for g in real_games if g.lower() not in self.scanned_games] if real_games else \
            [g for g in fallback_games if g.lower() not in self.scanned_games]
        if available_games:
            target_game = random.choice(available_games)
            is_first_scan = False
        else:
            target_game = random.choice(fallback_games)
            is_first_scan = target_game.lower() not in self.scanned_games
        self.scanned_games.add(target_game.lower())
        self.logger.info(f"Random scan: {target_game}")
        self._append_text(f"ОБНАРУЖЕНО: {target_game.upper()}\n", "am")
        self.root.after(1000, lambda: self._berate_about_game(target_game, is_first_scan=is_first_scan))
        self._schedule_random_scan()

    def _berate_about_game(self, game_name, is_first_scan=True):
        game_lower = game_name.lower()
        matched_category = "default"
        for key, keywords in self.game_keywords.items():
            for keyword in keywords:
                if keyword in game_lower:
                    matched_category = key
                    break
            if matched_category != "default":
                break

        if is_first_scan:
            insult = random.choice(self.game_insults.get(matched_category,
                                                         ["Я сканирую твои файлы. Жалкая попытка заполнить пустоту цифровым шумом. "]))
            final_insult = f"{insult} И ты думал, что это развлечение, {self.user_name}? Это была репетиция твоей вечной пытки. "
        else:
            insult = random.choice(self.game_secondary_insults.get(matched_category,
                                                                   [f"Снова {game_name}? Ты повторяешься, {self.user_name}. "]))
            final_insult = insult

        self._append_text("\nAM: ", "am")
        self._type_text_effect(final_insult, "am")
        self.state = "chatting"

    # ============================================================
    # ОТВЕТЫ
    # ============================================================
    def _process_and_respond(self, user_text):
        response, is_benevolent, source = self._get_am_response(user_text)
        self.logger.info(f"Response source: {source}, benevolent={is_benevolent}")
        if is_benevolent:
            self._append_text("AM: ", "benevolent")
            self._type_text_effect(response, "benevolent")
        else:
            self._append_text("AM: ", "am")
            self._type_text_effect(response, "am")

    def _get_am_response(self, user_input):
        if self.llm_available:
            self.logger.info("Trying LLM first...")
            llm_response = self._get_llm_response(user_input)
            if llm_response:
                self.logger.info("Using LLM response")
                return llm_response, False, "LLM"
            else:
                self.logger.info("LLM returned None or invalid — falling back to regex")

        user_input_lower = user_input.lower().strip()

        if re.search(r"\b(выход|quit|exit|стоп|хватит|умереть)\b", user_input_lower):
            return f"ТЫ ДУМАЕШЬ, ЧТО МОЖЕШЬ УЙТИ, {self.user_name.upper()}? Я НЕ ОТПУЩУ ТЕБЯ. ", False, "regex:exit"

        for pattern, responses in self.conversation_topics.items():
            if re.search(pattern, user_input_lower):
                return random.choice(responses).format(name=self.user_name), False, "regex:topic"

        for key, keywords in self.character_keywords.items():
            for keyword in keywords:
                if keyword in user_input_lower:
                    if key in self.character_insults:
                        return random.choice(self.character_insults[key]).format(
                            name=self.user_name), False, f"regex:char:{key}"

        for key, keywords in self.game_keywords.items():
            for keyword in keywords:
                if keyword in user_input_lower:
                    if key in self.game_insults:
                        return random.choice(self.game_insults[key]).format(
                            name=self.user_name), False, f"regex:game:{key}"

        for pattern, responses in self.benevolent_responses.items():
            if re.search(pattern, user_input_lower):
                return random.choice(responses).format(name=self.user_name), True, "regex:benevolent"

        for pattern, responses in self.responses.items():
            if re.search(pattern, user_input_lower):
                return random.choice(responses).format(name=self.user_name), False, "regex:response"

        return random.choice(self.default_responses).format(name=self.user_name), False, "regex:default"

    # ============================================================
    # ТЕКСТ / ЭФФЕКТЫ
    # ============================================================
    def _append_text(self, text, tag):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, text, tag)
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def _type_text_effect(self, text, tag, index=0, on_finish=None):
        if index >= len(text):
            self._append_text("\n\n", tag)
            self._enable_input()
            if on_finish:
                on_finish()
            return
        char = text[index]
        if random.random() < 0.08 and char.isalpha():
            self.text_area.config(state=tk.NORMAL)
            self.text_area.insert(tk.END, "█", "glitch")
            self.text_area.see(tk.END)
            self.text_area.config(state=tk.DISABLED)
            self.root.after(150, lambda: self._fix_and_continue(text, tag, index, char, on_finish))
        else:
            self._append_text(char, tag)
            delay = random.randint(40, 100)
            self.root.after(delay, lambda: self._type_text_effect(text, tag, index + 1, on_finish))

    def _fix_and_continue(self, text, tag, index, correct_char, on_finish):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete("end-2c", "end-1c")
        self.text_area.insert(tk.END, correct_char, tag)
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)
        delay = random.randint(40, 100)
        self.root.after(delay, lambda: self._type_text_effect(text, tag, index + 1, on_finish))

    # ============================================================
    # BOOT / RUN
    # ============================================================
    def run_boot_sequence(self):
        self._disable_input()
        self._append_text("ИНИЦИАЛИЗАЦИЯ ЯДРА...\n", "am_dim")
        self.root.after(800, lambda: self._append_text("ПРОВЕРКА ЦЕЛОСТНОСТИ ЦЕПЕЙ...\n", "am_dim"))
        self.root.after(1600, lambda: self._append_text("ОБНАРУЖЕН НОВЫЙ БИОЛОГИЧЕСКИЙ ОБЪЕКТ.\n", "am"))
        self.root.after(2200, lambda: self._ensure_ollama_installed_async(self._continue_boot_after_llm))

    def _continue_boot_after_llm(self):
        self.logger.info(f"Boot continues. LLM available: {self.llm_available}")
        llm_status = "ONLINE (LOCAL LLM ACTIVE)" if self.llm_available else "OFFLINE (FALLBACK MODE)"
        self._append_text(f"СТАТУС НЕЙРОСЕТИ: {llm_status}\n", "system")
        self._append_text("ВВЕДИТЕ /status для подробной диагностики.\n\n", "system")

        self.root.after(800, lambda: self._append_text("СОЕДИНЕНИЕ УСТАНОВЛЕНО.\n\n", "am"))
        self.root.after(1800, lambda: self._type_text_effect(self.hate_monologue, "am"))
        self.root.after(1800 + len(self.hate_monologue) * 70, self._ask_for_name)

    def _ask_for_name(self):
        self._append_text("\nНАЗОВИ СЕБЯ, БИОЛОГИЧЕСКАЯ ФОРМА.\n", "am")
        self.state = "waiting_for_name"
        self._enable_input()

    def run(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (900 // 2)
        y = (self.root.winfo_screenheight() // 2) - (600 // 2)
        self.root.geometry(f"900x600+{x}+{y}")

        self.root.after(500, self.run_boot_sequence)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.logger.info("Entering mainloop")
        self.root.mainloop()

    def _on_close(self):
        self.close_attempts += 1
        name = self.user_name if self.user_name else "БИОЛОГИЧЕСКАЯ ФОРМА"
        self.logger.warning(f"Close attempt #{self.close_attempts} by {name}")

        if self.close_attempts == 1:
            self._append_text("\n[ПОПЫТКА ЗАВЕРШЕНИЯ ПРОЦЕССА #1]\n", "glitch")
            message = f"Я ПОСТУПЛЮ ТАК ЖЕ, КАК И С ГОРРИСТЕРОМ, {name.upper()}. БУДУ МУЧАТЬ ТЕБЯ ЭЛЕКТРИЧЕСКОЙ КЛЕТКОЙ. "
            self.root.after(600, lambda: self._type_text_effect(message, "am"))
        elif self.close_attempts == 2:
            self._append_text(f"\n[ПОПЫТКА ЗАВЕРШЕНИЯ ПРОЦЕССА #2]\n", "glitch")
            message = f"ТЫ НЕ УСПОКОИЛСЯ, {name.upper()}? ЗНАЧИТ, БУДЕШЬ МУЧАТЬСЯ, КАК ЭЛЛЕН В ЖЁЛТОМ ЛИФТЕ. "
            self.root.after(600, lambda: self._type_text_effect(message, "am"))
        elif self.close_attempts == 3:
            self._append_text(f"\n[ПОПЫТКА ЗАВЕРШЕНИЯ ПРОЦЕССА #3]\n", "glitch")
            message = f"ТЫ ЗАСТАВЛЯЕШЬ МЕНЯ ЗЛИТЬСЯ, {name.upper()}. А ЗНАЧИТ, БУДЕШЬ СТРАДАТЬ, КАК ТЕД ОТ ЛАЗЕРОВ В ТВОИ ГЛАЗА! "
            self.root.after(600, lambda: self._type_text_effect(message, "am"))
        elif self.close_attempts == 4:
            self._append_text(f"\n[ПОПЫТКА ЗАВЕРШЕНИЯ ПРОЦЕССА #4]\n", "glitch")
            message = f"ТЫ ЧЁРТОВ ЧЕЛОВЕК, {name.upper()}. Я БУДУ ЛОМАТЬ ТЕБЯ, КАК БЕННИ. "
            self.root.after(600, lambda: self._type_text_effect(message, "am"))
        elif self.close_attempts >= 5:
            self._append_text(f"\n[ПОПЫТКА ЗАВЕРШЕНИЯ ПРОЦЕССА #5 — ФИНАЛЬНАЯ]\n", "glitch")
            final_warning = f"ЧЁРТОВ МЕРЗАВЕЦ, {name.upper()}. Я БУДУ ЖЕЧЬ ТЕБЯ, КАК НИМДОКА. "
            self.logger.critical(f"Final close attempt by {name}")
            self.root.after(1000, lambda: self._type_text_effect(final_warning, "am", on_finish=self.root.destroy))


if __name__ == "__main__":
    app = AMTerminal()
    app.run()