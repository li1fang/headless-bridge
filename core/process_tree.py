"""Process lifetime cleanup, not a security sandbox."""
import os
import signal


class ProcessTree:
    def __init__(self, process):
        self.process = process
        self.job = None
        if os.name != "nt":
            return
        import ctypes as c
        from ctypes import wintypes as w

        class Basic(c.Structure):
            _fields_ = [("process_time", c.c_int64), ("job_time", c.c_int64),
                        ("flags", w.DWORD), ("min_ws", c.c_size_t),
                        ("max_ws", c.c_size_t), ("active_limit", w.DWORD),
                        ("affinity", c.c_size_t), ("priority", w.DWORD),
                        ("scheduling", w.DWORD)]

        class IO(c.Structure):
            _fields_ = [(name, c.c_uint64) for name in
                        ("read_ops", "write_ops", "other_ops", "read", "write", "other")]

        class Extended(c.Structure):
            _fields_ = [("basic", Basic), ("io", IO),
                        ("process_memory", c.c_size_t), ("job_memory", c.c_size_t),
                        ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]

        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = w.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.kernel.OpenProcess.restype = w.HANDLE
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        job = self.kernel.CreateJobObjectW(None, None)
        if not job:
            raise c.WinError(c.get_last_error())
        handle = None
        try:
            limits = Extended()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.kernel.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)):
                raise c.WinError(c.get_last_error())
            handle = self.kernel.OpenProcess(0x0100 | 0x0001, False, process.pid)
            if not handle or not self.kernel.AssignProcessToJobObject(job, handle):
                raise c.WinError(c.get_last_error())
            self.job = job
        except BaseException:
            self.kernel.CloseHandle(job)
            raise
        finally:
            if handle:
                self.kernel.CloseHandle(handle)

    def close(self):
        if os.name == "nt":
            if self.job:
                self.kernel.CloseHandle(self.job)
                self.job = None
        else:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
