import json
import re
import shutil
from datetime import datetime
from operator import itemgetter
from pathlib import Path
from textwrap import dedent

from aiohttp_devtools.tools.sass_generator import SassGenerator
from jinja2 import Environment, FileSystemLoader, Markup

from utils import generate_description

MAN_SECTIONS = {
    1: 'User Commands',
    2: 'System calls',
    3: 'Library calls',
    4: 'Special files',
    5: 'File formats',
    6: 'Games',
    7: 'Miscellaneous',
    8: 'Admin commands',
}

POPULAR_COMMANDS = {
    'awk',
    'bash',
    'curl',
    'find',
    'grep',
    'iptables',
    'rsync',
    'sed',
}


class GenSite:
    def __init__(self):

        self.site_dir = Path('site')
        if self.site_dir.exists():
            shutil.rmtree(str(self.site_dir))

        self.env = Environment(
            loader=FileSystemLoader('templates'),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters['static'] = self._static_filter

        self.html_root = Path('data/html').resolve()
        self.pages = []
        self.now = datetime.now().strftime('%Y-%m-%d')

        with Path('data/man_metadata.json').open() as f:
            man_data = json.load(f)  # type List
        man_data.append({
            'description': 'blerp - FILTERS LOCAL OR REMOTE FILES OR RESOURCES USING PATTERNS',
            'extra1': '1692',
            'extra2': 'Imagination',
            'extra3': 'XKCD',
            'man_id': 1,
            'name': 'blerp',
            'raw_path': 'xkcd',
            'uri': 'man1/blerp',
        })
        man_data.sort(key=lambda v: (v['man_id'], v['name']))

        man_uris = {d['name']: d['uri'] for d in man_data}

        with Path('data/exec_data.json').open() as f:
            exec_data = json.load(f)

        exec_names = {d['name'] for d in exec_data.values() if d}

        for data in man_data:
            self.generate_man_page(data, exec_names)
        self.generate_man_lists(man_data)

        exec_data2 = []
        for data in exec_data.values():
            if data is not None:
                exec_data2.append(self.generate_exec_page(data, man_uris))
        self.generate_exec_list(exec_data2)

        with Path('data/builtin_metadata.json').open() as f:
            builtin_data = json.load(f)

        for data in builtin_data:
            self.generate_builtin_page(data)
        self.generate_builtin_list(builtin_data)

        self.generate_index(man_data, builtin_data, exec_data2)
        self.generate_extra()
        SassGenerator('styles', 'site/static/css').build()

    def _static_filter(self, path):
        return '/static/{}'.format(path.lstrip('/'))

    def render(self, rel_path: str, template: str, **context):
        template = self.env.get_template(template)

        assert rel_path and not rel_path.startswith('/'), repr(rel_path)
        if rel_path.endswith('/'):
            rel_path = '{}/index.html'.format(rel_path.rstrip('/'))
        path = self.site_dir / rel_path

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.render(**context))
        self.pages.insert(0, '/' + rel_path)

    def generate_man_page(self, ctx, exec_names):
        html_path = self.html_root / 'man' / '{raw_path}.html'.format(**ctx)
        try:
            html_path = html_path.resolve()
        except FileNotFoundError:
            print('{} does not exist'.format(html_path))
            return
        content = html_path.read_text()
        if '<h2>' in content[:200]:
            content = content[content.index('<h2>'):]
        content = re.sub('(</?)h2>', r'\1h4>', content)

        details = [(label, value) for label, value in [
            ('Man Section', Markup('{} &bull; {}'.format(ctx['man_id'], MAN_SECTIONS[ctx['man_id']]))),
            ('Document Date', ctx.get('doc_date')),
            ('extra &bull; 1 &bull; Version', ctx.get('extra1')),
            ('extra &bull; 2 &bull; Source', ctx.get('extra2')),
            ('extra &bull; 3 &bull; Book', ctx.get('extra3')),
        ] if value]
        man_comments = ctx.get('man_comments', None)

        ctx.update(
            page_title='man{man_id}/{name} | man page'.format(**ctx),
            title='{name} man page'.format(**ctx),
            content=content,
            man_comments=man_comments and dedent(man_comments),
            crumbs=[
                {'name': 'man{man_id}'.format(**ctx)},
            ],
            details=details,
            exec_variant=ctx['name'] in exec_names,
        )
        self.render(ctx['uri'].lstrip('/') + '/', 'man.jinja', **ctx)

    def generate_man_lists(self, data):
        pages = []
        man_id = 1
        data_iter = iter(data)
        while True:
            pdata = next(data_iter, None)
            if pdata is None or pdata['man_id'] != man_id:
                self.render(
                    'man{}/'.format(man_id),
                    'list.jinja',
                    title='man{}'.format(man_id),
                    description='{} - {}'.format(man_id, MAN_SECTIONS[man_id]),
                    pages=pages,
                )
                if pdata is None:
                    break
                else:
                    man_id = pdata['man_id']
                    pages = []
            pages.append(pdata)

    def generate_builtin_page(self, ctx):
        html_path = self.html_root / ctx['raw_path']
        try:
            html_path = html_path.resolve()
        except FileNotFoundError:
            print('{} does not exist'.format(html_path))
            return
        content = html_path.read_text()
        content = re.sub('(</?)h2>', r'\1h4>', content)

        ctx.update(
            page_title='builtin/{name} | man page'.format(**ctx),
            title='{name} man page'.format(**ctx),
            content=content,
            crumbs=[
                {'name': 'builtins'},
            ],
        )
        self.render(ctx['uri'].strip('/') + '/', 'builtin.jinja', **ctx)

    def generate_builtin_list(self, data):
        self.render(
            'builtin/',
            'list.jinja',
            title='Bash Builtins',
            description='Builtin bash methods',
            pages=data,
        )

    def generate_exec_page(self, ctx, man_uris):
        help_lines = ctx['help_msg'].strip('\n').split('\n')
        uri = 'help/{name}/'.format(**ctx)
        ctx.update(
            page_title='help/{name} | help page'.format(**ctx),
            title='{name} help page'.format(**ctx),
            description=generate_description(help_lines[0], help_lines[1:10]),
            crumbs=[
                {'name': 'help'},
            ],
            man_variant_uri=man_uris.get(ctx['name'], None),
            uri=uri,
        )
        self.render(uri.lstrip('/'), 'exec.jinja', **ctx)
        return ctx

    def _sort_help(self, data):
        return sorted(data, key=itemgetter('name'))

    def generate_exec_list(self, data):
        self.render(
            'help/',
            'list.jinja',
            title='Help Output',
            description='Output of help commands',
            pages=self._sort_help(data),
        )

    def generate_index(self, man_data, builtin_data, exec_data):
        self.render(
            'index.html',
            'index.jinja',
            title='helpmanual.io',
            description='man pages and help text for unix commands',
            skip_final_crumb=True,
            sections=[
                dict(
                    title='GNU manual pages',
                    description='GNU man pages in 8 sections',
                    links=[{
                        'uri': 'man{}'.format(man_id),
                        'name': 'man{}'.format(man_id),
                        'description': MAN_SECTIONS[man_id],
                    } for man_id in range(1, 9)],
                ),
                dict(
                    title='Bash Builtins',
                    description='Builtin bash methods',
                    links=[b for b in builtin_data[:9] if len(b['name']) > 1],
                    more='/builtin',
                ),
                dict(
                    title='Help Output',
                    description='Output of help commands',
                    links=[p for p in self._sort_help(exec_data) if p['name'] in POPULAR_COMMANDS],
                    more='/help',
                ),
            ]
        )

    def generate_extra(self):
        self.render('sitemap.xml', 'sitemap.xml.jinja', pages=self.pages, now=self.now)
        self.render('robots.txt', 'robots.txt.jinja')
        self.render('humans.txt', 'humans.txt.jinja', now=self.now)
        self.render('404.html', 'stub.jinja', title='404', description='Page not found.', skip_final_crumb=True)


if __name__ == '__main__':
    GenSite()

