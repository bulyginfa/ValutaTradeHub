"""Планировщик обновления курсов валют"""

from __future__ import annotations

import logging
from threading import Event, Thread

from .config import ParserConfig
from .updater import RatesUpdater


class RatesScheduler:
	"""Фоновый планировщик обновления курсов с заданным интервалом."""
	def __init__(
		self,
		update_interval: int = 300,
		updater: RatesUpdater | None = None,
		config: ParserConfig | None = None,
	) -> None:
		"""Подготовить планировщик и создать updater при необходимости."""
		self.update_interval = update_interval
		self.updater = updater or RatesUpdater(config=config)
		self.stop_event = Event()
		self.thread: Thread | None = None
		self.logger = logging.getLogger("valutatrade_hub.parser_service")

	def start(self) -> None:
		"""Запустить фоновый поток обновлений."""
		if self.thread and self.thread.is_alive():
			self.logger.warning("Планировщик уже запущен")
			return

		self.stop_event.clear()
		self.thread = Thread(target=self._run, daemon=True)
		self.thread.start()
		self.logger.info("Планировщик запущен с интервалом %sс", self.update_interval)

	def stop(self) -> None:
		"""Остановить фоновый поток обновлений."""
		self.stop_event.set()
		if self.thread:
			self.thread.join(timeout=5)
		self.logger.info("Планировщик остановлен")

	def run_once(self) -> None:
		"""Выполнить одно обновление курсов вручную."""
		try:
			self.updater.run_update()
			self.logger.info("Ручное обновление завершено")
		except Exception as exc:
			self.logger.error("Ошибка ручного обновления: %s", exc)

	def _run(self) -> None:
		"""Основной цикл: обновлять и ждать следующий интервал."""
		while not self.stop_event.is_set():
			self.run_once()
			self.stop_event.wait(self.update_interval)
