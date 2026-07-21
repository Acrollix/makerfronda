from __future__ import annotations

import io
import json
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QImage

from .adaptive import DisplayProfile, ViewportMetrics, calculate_layout, screen_identifier
from .rendering import CoverRenderer, RenderError, RenderRequest, safe_filename, save_png_atomic
from .settings import Settings, SettingsStore
from .template import TemplateCompiler, TemplateError, TemplateProfile
from .paths import app_data_dir, built_in_template_path, cache_dir, default_export_dir, is_macos_app_bundle_path


class AppController(QObject):
    changed = Signal()
    toast = Signal(str, str)
    errorOccurred = Signal(str)
    profileChanged = Signal()
    previewFinished = Signal(int, str, str)
    exportProgressed = Signal(int, int, int)
    exportFinished = Signal(int, int, bool, str)

    def __init__(self) -> None:
        super().__init__()
        self.store = SettingsStore()
        self.settings: Settings = self.store.load()
        default_output = default_export_dir()
        # Migrate the previous default (the application directory itself) to
        # the explicit `Готово` folder. A user-selected different folder is
        # preserved unchanged.
        saved_output = Path(self.settings.export_path) if self.settings.export_path else None
        if (
            not saved_output
            or saved_output.resolve() == default_output.parent.resolve()
            or is_macos_app_bundle_path(saved_output)
        ):
            # Older macOS previews put «Готово» in the .app bundle. Finder can
            # mount a downloaded app read-only through App Translocation, so
            # migrate that obsolete location to the user-visible Pictures path.
            self.settings.export_path = str(default_output)
        else:
            # A rebuild replaces the portable release directory. Recreate the
            # remembered output directory on the next start instead of leaving
            # a valid-looking but absent `Готово` path in the UI.
            Path(self.settings.export_path).mkdir(parents=True, exist_ok=True)
        self.compiler = TemplateCompiler()
        self.profile: TemplateProfile | None = None
        self.renderer: CoverRenderer | None = None
        # Original artwork is normalised once to temporary PNG files. Keeping
        # an RGBA bitmap per series in memory made long projects consume GBs.
        self._artwork_dir = app_data_dir() / "session-artwork"
        self._artwork_dir.mkdir(parents=True, exist_ok=True)
        self._session_path = app_data_dir() / "session.json"
        self.episode_images: dict[int, Path] = {}
        self.shared_image: Path | None = None
        self._artwork_serial = 0
        self._title = ""
        # Centre is the canonical FRONDA layout and gives identical output on
        # every machine; the user can still explicitly choose left alignment.
        self._title_alignment = "center"
        self._start_episode = 1
        self._end_episode = 1
        self._preview_episode = 1
        self._preview_url = ""
        self._status = "Выберите PSD-шаблон"
        self._last_error = ""
        self._screen_key = "current"
        self._display_profile = self.settings.display_profiles.get(self._screen_key, "Auto")
        self._release_type = self.settings.release_type if self.settings.release_type in {"Episode", "Film"} else "Episode"
        self._artwork_mode = self.settings.artwork_mode if self.settings.artwork_mode in {"Shared", "PerEpisode"} else "PerEpisode"
        self._template_mode = self.settings.template_mode if self.settings.template_mode in {"Builtin", "Custom"} else "Builtin"
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(450)
        self._preview_timer.timeout.connect(self._render_preview_async)
        self._preview_generation = 0
        self._preview_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fronda-preview")
        self._export_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fronda-export")
        self._export_cancel = Event()
        self._export_token = 0
        self._exporting = False
        self._export_progress = 0
        self._export_total = 0
        self.previewFinished.connect(self._apply_preview_result)
        self.exportProgressed.connect(self._apply_export_progress)
        self.exportFinished.connect(self._apply_export_finished)
        QGuiApplication.instance().aboutToQuit.connect(self.shutdown)
        self._restore_session()
        if self._template_mode == "Builtin":
            self.settings.template_path = str(built_in_template_path())
        if self.settings.template_path:
            QTimer.singleShot(0, self.analyzeTemplate)

    def _save(self) -> None:
        self.settings.display_profiles[self._screen_key] = self._display_profile
        try:
            self.store.save(self.settings)
        except OSError as exc:
            self._last_error = f"Не удалось сохранить настройки: {exc}"
            self.toast.emit("Настройки не сохранены", "error")

    @Property(str, notify=changed)
    def templatePath(self) -> str:
        return self.settings.template_path

    @Property(str, notify=changed)
    def templateMode(self) -> str:
        return self._template_mode

    @Property(str, notify=changed)
    def exportPath(self) -> str:
        return self.settings.export_path

    @Property(str, notify=changed)
    def title(self) -> str:
        return self._title

    @Property(str, notify=changed)
    def titleAlignment(self) -> str:
        return self._title_alignment

    @Property(int, notify=changed)
    def startEpisode(self) -> int:
        return self._start_episode

    @Property(int, notify=changed)
    def endEpisode(self) -> int:
        return self._end_episode

    @Property(int, notify=changed)
    def previewEpisode(self) -> int:
        return self._preview_episode

    @Property(str, notify=changed)
    def previewUrl(self) -> str:
        return self._preview_url

    @Property(str, notify=changed)
    def status(self) -> str:
        return self._status

    @Property(str, notify=changed)
    def lastError(self) -> str:
        return self._last_error

    @Property(bool, notify=changed)
    def hasImage(self) -> bool:
        return self._image_for_episode(self._preview_episode) is not None

    @Property(bool, notify=changed)
    def readyToExport(self) -> bool:
        return bool(not self._exporting and self.renderer and self._title.strip() and self.settings.export_path and self._start_episode <= self._end_episode and all(self._image_for_episode(episode) is not None for episode in range(self._start_episode, self._end_episode + 1)))

    @Property(bool, notify=changed)
    def exporting(self) -> bool:
        return self._exporting

    @Property(int, notify=changed)
    def exportProgress(self) -> int:
        return self._export_progress

    @Property(int, notify=changed)
    def exportTotal(self) -> int:
        return self._export_total

    @Property(bool, notify=changed)
    def reduceMotion(self) -> bool:
        return self.settings.reduce_motion

    @Property(str, notify=profileChanged)
    def displayProfile(self) -> str:
        return self._display_profile

    @Property(str, notify=changed)
    def releaseType(self) -> str:
        return self._release_type

    @Property(str, notify=changed)
    def releaseLabel(self) -> str:
        return "ФИЛЬМ" if self._release_type == "Film" else "ЭПИЗОД"

    @Property(str, notify=changed)
    def artworkMode(self) -> str:
        return self._artwork_mode

    def _image_for_episode(self, episode: int) -> Path | None:
        path = self.shared_image if self._artwork_mode == "Shared" else self.episode_images.get(episode)
        return path if path and path.is_file() else None

    @staticmethod
    def _load_artwork(path: Path) -> Image.Image:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            image.load()
            return image

    def _store_artwork(self, image: Image.Image, episode: int | None) -> Path:
        self._artwork_serial += 1
        name = f"shared-{self._artwork_serial}.png" if episode is None else f"episode-{episode:04d}-{self._artwork_serial}.png"
        target = self._artwork_dir / name
        temporary = target.with_suffix(".tmp")
        image.save(temporary, "PNG")
        temporary.replace(target)
        return target

    def _discard_artwork_if_unused(self, path: Path | None) -> None:
        if not path or path.parent != self._artwork_dir:
            return
        active = {item for item in self.episode_images.values()}
        if self.shared_image:
            active.add(self.shared_image)
        if path not in active:
            path.unlink(missing_ok=True)

    def _restore_session(self) -> None:
        try:
            payload = json.loads(self._session_path.read_text(encoding="utf-8"))
            self._title = str(payload.get("title", ""))
            self._title_alignment = payload.get("title_alignment", "center") if payload.get("title_alignment") in {"left", "center"} else "center"
            self._start_episode = max(0, int(payload.get("start_episode", 1)))
            self._end_episode = max(self._start_episode, int(payload.get("end_episode", self._start_episode)))
            self._preview_episode = min(self._end_episode, max(self._start_episode, int(payload.get("preview_episode", self._start_episode))))
            self._release_type = payload.get("release_type", self._release_type) if payload.get("release_type") in {"Episode", "Film"} else self._release_type
            self._artwork_mode = payload.get("artwork_mode", self._artwork_mode) if payload.get("artwork_mode") in {"Shared", "PerEpisode"} else self._artwork_mode
            self._template_mode = payload.get("template_mode", self._template_mode) if payload.get("template_mode") in {"Builtin", "Custom"} else self._template_mode
            if self._template_mode == "Custom":
                template = Path(str(payload.get("template_path", "")))
                if template.is_file():
                    self.settings.template_path = str(template)
            shared = Path(str(payload.get("shared_image", "")))
            self.shared_image = shared if shared.is_file() else None
            self.episode_images = {
                int(key): path for key, value in payload.get("episode_images", {}).items()
                if int(key) >= 0 and (path := Path(str(value))).is_file()
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return

    def _save_session(self) -> None:
        payload = {
            "version": 1,
            "template_path": self.settings.template_path,
            "template_mode": self._template_mode,
            "title": self._title,
            "title_alignment": self._title_alignment,
            "start_episode": self._start_episode,
            "end_episode": self._end_episode,
            "preview_episode": self._preview_episode,
            "release_type": self._release_type,
            "artwork_mode": self._artwork_mode,
            "shared_image": str(self.shared_image) if self.shared_image else "",
            "episode_images": {str(key): str(value) for key, value in self.episode_images.items() if value.is_file()},
        }
        temporary = self._session_path.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self._session_path)
        except OSError:
            temporary.unlink(missing_ok=True)

    @Slot()
    def shutdown(self) -> None:
        self._export_cancel.set()
        self._preview_executor.shutdown(wait=False, cancel_futures=True)
        self._export_executor.shutdown(wait=False, cancel_futures=True)

    @Slot(str)
    def setTemplatePath(self, value: str) -> None:
        self.settings.template_path = QUrl(value).toLocalFile() if value.startswith("file:") else value
        self._template_mode = "Custom"
        self.settings.template_mode = "Custom"
        self._status = "Шаблон ожидает проверки"
        self._save(); self._save_session(); self.changed.emit()

    @Slot(str)
    def setTemplateMode(self, value: str) -> None:
        if value not in {"Builtin", "Custom"} or value == self._template_mode:
            return
        self._template_mode = value
        self.settings.template_mode = value
        if value == "Builtin":
            template = built_in_template_path()
            if not template.is_file():
                self._report_error("Встроенный шаблон не найден.")
                return
            self.settings.template_path = str(template)
            self._status = "Выбран встроенный шаблон FRONDA"
        else:
            # Never silently export with the old built-in PSD after the user
            # has explicitly asked to work with another template.
            self.settings.template_path = ""
            self.profile = self.renderer = None
            self._preview_url = ""
            self._status = "Выберите другой PSD-шаблон"
        self._save(); self._save_session(); self.changed.emit()
        if value == "Builtin":
            self.analyzeTemplate()

    def _report_error(self, message: str, exc: Exception | None = None) -> None:
        """Show failures in a permanent dialog and retain a local diagnostic."""
        detail = message if exc is None else f"{message}\n\nТехническая информация:\n{type(exc).__name__}: {exc}"
        self._last_error = detail
        self._status = message.split("\n", 1)[0]
        try:
            with (cache_dir().parent / "errors.log").open("a", encoding="utf-8") as log:
                log.write(detail + "\n" + "─" * 48 + "\n")
        except OSError:
            pass
        self.toast.emit(self._status, "error")
        self.errorOccurred.emit(detail)

    @Slot()
    def copyLastError(self) -> None:
        if self._last_error:
            QGuiApplication.clipboard().setText(self._last_error)

    @Slot(str)
    def setExportPath(self, value: str) -> None:
        self.settings.export_path = QUrl(value).toLocalFile() if value.startswith("file:") else value
        self._save(); self._save_session(); self.changed.emit()

    @Slot(str)
    def setTitle(self, value: str) -> None:
        self._title = value
        self._save_session(); self.changed.emit(); self.updatePreview()

    @Slot(str)
    def setTitleAlignment(self, value: str) -> None:
        if value in {"left", "center"}:
            self._title_alignment = value
            self._save_session(); self.changed.emit(); self.updatePreview()

    @Slot(str)
    def setReleaseType(self, value: str) -> None:
        if value in {"Episode", "Film"} and value != self._release_type:
            self._release_type = value
            if value == "Film":
                # A film is a single cover with a single artwork; series-only
                # artwork choices and extra episode copies are not applicable.
                if self.shared_image is None:
                    self.shared_image = self._image_for_episode(self._preview_episode) or next(iter(self.episode_images.values()), None)
                self._artwork_mode = "Shared"
                self._end_episode = self._start_episode
                self._preview_episode = self._start_episode
                self.settings.artwork_mode = "Shared"
            self.settings.release_type = value
            self._save()
            self._save_session(); self.changed.emit(); self.updatePreview()

    @Slot(str)
    def setArtworkMode(self, value: str) -> None:
        if value in {"Shared", "PerEpisode"} and value != self._artwork_mode:
            if value == "Shared" and self.shared_image is None:
                # Promote the currently edited cover (or the first available
                # one) so switching modes never discards the user's work.
                self.shared_image = self.episode_images.get(self._preview_episode) or next(iter(self.episode_images.values()), None)
            self._artwork_mode = value
            if value == "Shared":
                self._preview_episode = self._start_episode
            self.settings.artwork_mode = value
            self._save()
            self._save_session(); self.changed.emit(); self.updatePreview()

    @Slot(int)
    def setStartEpisode(self, value: int) -> None:
        self._start_episode = max(0, value)
        if self._end_episode < self._start_episode: self._end_episode = self._start_episode
        if self._preview_episode < self._start_episode: self._preview_episode = self._start_episode
        self._save_session(); self.changed.emit(); self.updatePreview()

    @Slot(int)
    def setEndEpisode(self, value: int) -> None:
        self._end_episode = max(self._start_episode, value)
        if self._preview_episode > self._end_episode: self._preview_episode = self._end_episode
        self._save_session(); self.changed.emit(); self.updatePreview()

    @Slot(int)
    def setPreviewEpisode(self, value: int) -> None:
        episode = max(self._start_episode, min(self._end_episode, value))
        if episode != self._preview_episode:
            self._preview_episode = episode
            self._save_session(); self.changed.emit(); self.updatePreview()

    @Slot(bool)
    def setReduceMotion(self, value: bool) -> None:
        self.settings.reduce_motion = value
        self._save(); self.changed.emit()

    @Slot(str)
    def setDisplayProfile(self, value: str) -> None:
        if value in {item.value for item in DisplayProfile}:
            self._display_profile = value
            self._save(); self.profileChanged.emit()

    @Slot(str)
    def setScreenKey(self, description: str) -> None:
        key = screen_identifier(description)
        if key != self._screen_key:
            self._screen_key = key
            self._display_profile = self.settings.display_profiles.get(key, "Auto")
            self.profileChanged.emit()

    @Slot()
    def analyzeTemplate(self) -> None:
        try:
            cached = self.compiler.load(self.settings.template_path)
            self.profile = cached or self.compiler.compile(self.settings.template_path)
            self.renderer = CoverRenderer(self.profile)
            self._last_error = ""
            self._status = f"Шаблон готов: {self.profile.canvas_width} × {self.profile.canvas_height}"
            static_preview = Path(self.profile.cache_path) / "static.png"
            self._preview_url = QUrl.fromLocalFile(str(static_preview)).toString() + f"?v={static_preview.stat().st_mtime_ns}"
            self.toast.emit("Шаблон готов", "success")
        except Exception as exc:
            self.profile = self.renderer = None
            self._report_error(f"Не удалось прочитать PSD-шаблон: {exc}", exc)
        self.changed.emit(); self.updatePreview()

    @Slot()
    def pasteImage(self) -> None:
        mime = QGuiApplication.clipboard().mimeData()
        if not mime or not mime.hasImage():
            self._report_error("В буфере обмена нет изображения.")
            return
        qimage = QGuiApplication.clipboard().image()
        if qimage.isNull():
            self._report_error("Не удалось прочитать изображение из буфера.")
            return
        try:
            raw = QByteArray()
            buffer = QBuffer(raw)
            buffer.open(QIODevice.WriteOnly)
            if not qimage.save(buffer, "PNG"):
                raise OSError("Qt не смог сохранить изображение из буфера")
            buffer.close()
            image = Image.open(io.BytesIO(bytes(raw))).convert("RGBA")
            image.load()
            if self._artwork_mode == "Shared":
                previous = self.shared_image
                self.shared_image = self._store_artwork(image, None)
                self._discard_artwork_if_unused(previous)
            else:
                previous = self.episode_images.get(self._preview_episode)
                self.episode_images[self._preview_episode] = self._store_artwork(image, self._preview_episode)
                self._discard_artwork_if_unused(previous)
        except Exception as exc:
            self._report_error(f"Не удалось обработать изображение: {exc}", exc)
            return
        self._status = "Общее изображение добавлено для всех выпусков" if self._artwork_mode == "Shared" else f"Изображение добавлено для серии {self._preview_episode}"
        self.toast.emit(self._status, "success")
        self._save_session(); self.changed.emit(); self.updatePreview()

    @Slot(str)
    def setImagePath(self, value: str) -> None:
        source = Path(QUrl(value).toLocalFile() if value.startswith("file:") else value)
        try:
            if not source.is_file():
                raise OSError("файл не найден")
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGBA")
                image.load()
                if self._artwork_mode == "Shared":
                    previous = self.shared_image
                    self.shared_image = self._store_artwork(image, None)
                    self._discard_artwork_if_unused(previous)
                else:
                    previous = self.episode_images.get(self._preview_episode)
                    self.episode_images[self._preview_episode] = self._store_artwork(image, self._preview_episode)
                    self._discard_artwork_if_unused(previous)
            self._last_error = ""
            target = "для всех выпусков" if self._artwork_mode == "Shared" else f"для серии {self._preview_episode}"
            self._status = f"Изображение добавлено {target}: {source.name}"
            self.toast.emit("Изображение добавлено", "success")
        except Exception as exc:
            self._report_error(f"Не удалось открыть изображение: {exc}", exc)
        self._save_session(); self.changed.emit(); self.updatePreview()

    @Slot()
    def updatePreview(self) -> None:
        # Invalidate any result already running in the worker. This prevents a
        # preview for the previous episode/template from appearing after the
        # user has switched to an empty episode or another PSD.
        self._preview_generation += 1
        self._preview_timer.stop()
        if not self.renderer:
            return
        if self._image_for_episode(self._preview_episode) is None or not self._title.strip():
            static_preview = Path(self.profile.cache_path) / "static.png"  # type: ignore[union-attr]
            self._preview_url = QUrl.fromLocalFile(str(static_preview)).toString() + f"?v={static_preview.stat().st_mtime_ns}"
            self.changed.emit()
            return
        # Rendering a 1920×1080 PSD composition on every key press blocks the
        # event loop. Wait until typing pauses, then render outside the UI.
        self._preview_timer.start()

    @Slot()
    def _render_preview_async(self) -> None:
        if not (self.renderer and self._image_for_episode(self._preview_episode) is not None and self._title.strip() and self.profile):
            return
        generation = self._preview_generation
        renderer = self.renderer
        artwork = self._image_for_episode(self._preview_episode)
        assert artwork is not None
        title = self._title.strip()
        episode = self._preview_episode
        alignment = self._title_alignment
        release_type = self._release_type
        output = Path(self.profile.cache_path) / f"preview-{generation}.png"

        def render() -> tuple[int, str, str]:
            try:
                image = self._load_artwork(artwork)
                preview = renderer.render(RenderRequest(title, episode, image, alignment, release_type))
                preview.save(output, "PNG")
                return generation, QUrl.fromLocalFile(str(output)).toString() + f"?v={output.stat().st_mtime_ns}", ""
            except Exception as exc:
                return generation, "", f"Ошибка предпросмотра: {exc}\n\nТехническая информация:\n{type(exc).__name__}: {exc}"

        future = self._preview_executor.submit(render)
        future.add_done_callback(lambda job: self.previewFinished.emit(*job.result()))

    @Slot(int, str, str)
    def _apply_preview_result(self, generation: int, url: str, error: str) -> None:
        if generation != self._preview_generation:
            return
        if error:
            self._report_error(error)
        else:
            self._preview_url = url
            # Keep only the currently displayed preview. Without cleanup,
            # normal typing produces hundreds of full-resolution PNG files.
            if self.profile:
                current = Path(QUrl(url.split("?", 1)[0]).toLocalFile()).resolve()
                for old in Path(self.profile.cache_path).glob("preview-*.png"):
                    if old.resolve() != current:
                        old.unlink(missing_ok=True)
        self.changed.emit()

    @Slot()
    def exportCovers(self) -> None:
        if not self.readyToExport:
            missing: list[str] = []
            if not self.renderer:
                missing.append("проверенный PSD-шаблон")
            if not self._title.strip():
                missing.append("название релиза")
            absent = [str(episode) for episode in range(self._start_episode, self._end_episode + 1) if self._image_for_episode(episode) is None]
            if absent:
                missing.append("изображения для серий: " + ", ".join(absent[:8]) + ("…" if len(absent) > 8 else ""))
            if not self.settings.export_path:
                missing.append("папка экспорта")
            if self._start_episode > self._end_episode:
                missing.append("корректный диапазон серий")
            self._report_error("Нельзя создать обложки. Заполните: " + ", ".join(missing) + ".")
            return
        assert self.renderer
        episodes = list(range(self._start_episode, self._end_episode + 1))
        sources = {episode: self._image_for_episode(episode) for episode in episodes}
        renderer = self.renderer
        title = self._title
        alignment = self._title_alignment
        release_type = self._release_type
        destination = Path(self.settings.export_path)
        overwrite = self.settings.overwrite_existing
        self._export_token += 1
        token = self._export_token
        self._export_cancel.clear()
        self._exporting = True
        self._export_progress = 0
        self._export_total = len(episodes)
        self._status = f"Подготовка экспорта: 0/{self._export_total}"
        self.changed.emit()

        def export() -> None:
            completed = 0
            try:
                for episode in episodes:
                    if self._export_cancel.is_set():
                        self.exportFinished.emit(token, completed, True, "")
                        return
                    source = sources[episode]
                    assert source is not None
                    image = self._load_artwork(source)
                    rendered = renderer.render(RenderRequest(title, episode, image, alignment, release_type))
                    suffix = "Фильм" if release_type == "Film" else f"Эпизод {episode}"
                    filename = f"{safe_filename(title)} — {suffix}.png"
                    save_png_atomic(rendered, destination / filename, overwrite)
                    completed += 1
                    self.exportProgressed.emit(token, completed, len(episodes))
                self.exportFinished.emit(token, completed, False, "")
            except Exception as exc:
                self.exportFinished.emit(token, completed, False, f"Не удалось создать обложки: {exc}\n\nТехническая информация:\n{type(exc).__name__}: {exc}")

        self._export_executor.submit(export)

    @Slot()
    def cancelExport(self) -> None:
        if self._exporting:
            self._export_cancel.set()
            self._status = "Отмена экспорта…"
            self.changed.emit()

    @Slot(int, int, int)
    def _apply_export_progress(self, token: int, current: int, total: int) -> None:
        if token != self._export_token:
            return
        self._export_progress, self._export_total = current, total
        self._status = f"Экспорт: {current}/{total}"
        self.changed.emit()

    @Slot(int, int, bool, str)
    def _apply_export_finished(self, token: int, completed: int, cancelled: bool, error: str) -> None:
        if token != self._export_token:
            return
        self._exporting = False
        if error:
            self._report_error(error)
        elif cancelled:
            self._status = f"Экспорт отменён: создано {completed} из {self._export_total}"
            self.toast.emit(self._status, "error")
        else:
            self._export_progress = self._export_total
            self._status = f"Создано обложек: {completed}"
            self.toast.emit(self._status, "success")
        self.changed.emit()

    @Slot(float, float, float, float, bool, bool, float, float, result="QVariant")
    def layoutFor(self, width: float, height: float, available_width: float, available_height: float, maximized: bool, fullscreen: bool, diagonal: float, dpr: float) -> dict:
        state = calculate_layout(
            ViewportMetrics(width, height, available_width, available_height, dpr=max(1.0, dpr), physical_diagonal_inches=diagonal, maximized=maximized, fullscreen=fullscreen),
            DisplayProfile(self._display_profile),
        )
        return state.to_dict()
