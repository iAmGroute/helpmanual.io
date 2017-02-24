#!/usr/bin/env python3.6
"""
Get "--help" and "--version" (or equivalent) info from all commands.

**BIG FAT WARNING**: this can fuck things up, both filesystem and kill the x session.
Run with caution.
"""
import json
import logging
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from subprocess import run, PIPE

from tqdm import tqdm

from utils import DATA_DIR
from findhelp import process_cmd
from help_logging import start_logging

logger = logging.getLogger('exec_help')

THREADS = 7
MAX_COMMANDS = int(os.getenv('MAX_COMMANDS', 0))

THIS_DIR = Path(__file__).parent.resolve()

start_logging()

logger = logging.getLogger('exec_help.start')


class ExecHelp:
    def __init__(self):
        self.commands = self.run_bash('compgen -c')
        self.commands = {c for c in self.commands.split('\n') if c}
        for arg in ['builtin', 'keyword']:
            v = self.run_bash('compgen -A ' + arg)
            self.commands -= {c for c in v.split('\n') if c}
        logger.info('found {} commands'.format(len(self.commands)))
        self.data_path = DATA_DIR / 'exec_data.json'
        self.data = {}
        if self.data_path.exists():
            with self.data_path.open() as f:
                self.data = json.load(f)
        self.commands = sorted({c for c in self.commands if c not in self.data})
        logger.info('found {} commands left to run, MAX_COMMANDS=%s'.format(len(self.commands)), MAX_COMMANDS)
        self.proc = None
        self.queue = None
        self.new_cmds = []
        self.started = 0

        self.executor = str((THIS_DIR / 'findhelp.py').resolve())
        self.json_dir = Path('/tmp/findhelp')
        if self.json_dir.exists():
            shutil.rmtree(str(self.json_dir))

        try:
            self.go()
        finally:
            self.write()
            print('generated info for {} commands'.format(len(self.new_cmds)))

    def write(self):
        with self.data_path.open('w') as f:
            json.dump(self.data, f, sort_keys=True, indent=2)

    def worker(self):
        while True:
            command = self.queue.get()
            if command is None:
                break
            try:
                self.process_cmd(command)
                self.new_cmds.append(command)
                if len(self.new_cmds) % 5 == 0:
                    self.write()
            finally:
                self.queue.task_done()

    def go(self):
        sandpit = Path('/tmp/sandpit')
        if sandpit.exists():
            shutil.rmtree(str(sandpit))

        self.queue = queue.Queue(maxsize=10)
        threads = []
        for i in range(THREADS):
            t = threading.Thread(target=self.worker)
            t.start()
            threads.append(t)

        command_count = len(self.commands)
        # for command in tqdm(self.commands):
        for command in self.commands:
            logger.info('%d/%d %0.2f%% "%s"', self.started, command_count, self.started / command_count * 100, command)
            self.queue.put(command)
            self.started += 1
            if MAX_COMMANDS and self.started > MAX_COMMANDS:
                break

        logger.info('waiting for %s queued jobs to finish', self.queue.qsize())
        self.queue.join()

        for i in range(THREADS):
            self.queue.put(None)

        for t in threads:
            t.join()

    def process_cmd(self, command):
        self.data[command] = process_cmd(command)
        subprocess.run(('stty', 'sane'))
        # outpath = self.json_dir / '{}.json'.format(command)
        # cmd = '{} {} {}'.format(self.executor, command, outpath)
        # run(['xterm', '-e', cmd], check=True)
        # if not outpath.exists():
        #     raise RuntimeError('"{}" does not exist, command: "{}"'.format(outpath, cmd))
        # with outpath.open() as f:
        #     data = json.load(f)
        # self.data[command] = data

    def run_bash(self, cmd):
        p = run(cmd, executable='/bin/bash', stdout=PIPE, stderr=PIPE,
                shell=True, universal_newlines=True)
        if p.returncode != 0:
            raise RuntimeError('"{}" failed, return code {}\nstderr:{}'.format(cmd, p.returncode, p.stderr))
        return p.stdout


if __name__ == '__main__':
    ExecHelp()
