import time

class Status:
    def __init__(self, on_change=None):
        self.step = None
        self.process = None
        self.state = "idle"
        self.history = []
        self.on_change = on_change

    def update(self, step, process, state="running"):
        self.step = step
        self.process = process
        self.state = state
        self.history.append({"step": step, "process": process, "state": state, "time": time.time()})

        if self.on_change:
            self.on_change(self.current())

    def done(self, step=None, process="Completed"):
        self.update(step or self.step, process, "done")

    def fail(self, error, step=None):
        self.update(step or self.step, str(error), "failed")

    def current(self):
        return {"step": self.step, "process": self.process, "state": self.state}