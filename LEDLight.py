import threading
import time
import tkinter as tk

class StatusLED:
    def __init__(
            self,
            master,
            size=20,
            idle_color="#33cc33",
            blink_color="#ff9900",
            off_color="grey",
            blink_interval=500
    ):
        self.canvas = tk.Canvas(master, width=size, height=size, highlightthickness=0)
        self.led = self.canvas.create_oval(2, 2, size-2, size-2, fill=idle_color, outline="")
        self.canvas.pack(side="left", padx=(8,0))

        self.idle_color    = idle_color
        self.blink_color   = blink_color
        self.off_color     = off_color
        self.blink_interval= blink_interval

        self._blinking = False
        self._state_on  = False
        self._job       = None

    def start_blink(self):
        if self._blinking:
            return
        self._blinking = True
        self._state_on = False
        self._toggle()

    def stop_blink(self):
        self._blinking = False
        if self._job is not None:
            self.canvas.after_cancel(self._job)
            self._job = None
        self.canvas.itemconfigure(self.led, fill=self.idle_color)

    def _toggle(self):
        if not self._blinking:
            return
        self._state_on = not self._state_on
        new_color = self.blink_color if self._state_on else self.off_color
        self.canvas.itemconfigure(self.led, fill=new_color)
        self._job = self.canvas.after(self.blink_interval, self._toggle)


def fake_long_task(done_callback):
    time.sleep(5)
    done_callback()
