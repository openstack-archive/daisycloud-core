#!/usr/bin/env python
# coding: utf-8

"""

    diff-coverage

    Copyright (c) 2012, Preston Holmes and other contributors.
    All rights reserved.

    Mainly from https://github.com/ptone/diff-coverage, with modifications to
    fit the daisycloud-core project directory arrangement.

    This module will, in a somewhat inflexible way, compare a diff coverage.py
    data to determine whether lines added or modified in the diff, were executed
    during a coverage session.

    requires http://python-patch.googlecode.com/svn/trunk/patch.py
    which is included in this package with attribution

"""

from collections import defaultdict
from optparse import OptionParser
import coverage
import logging
import os
import patch
import re
import sys
import webbrowser
from pprint import pprint


solution_path = os.path.abspath(".")
coverage_html_dir = os.path.join(os.getcwd(), 'diff_coverage_html')
line_end = '(?:\n|\r\n?)'

patch_logger = logging.getLogger('patch')
patch_logger.addHandler(logging.NullHandler())

PATH_FIX = '^[a|b]{1,2}/'
# pattern to use to insert new stylesheet
# this is currently pretty brittle - but lighterweight than doing something with
# lxml and/or pyquery
current_style = "<link rel='stylesheet' href='style.css' type='text/css'>"

def parse_patch(patch_file, sub_code_path):
    """
    returns a dictionary of {filepath:[lines patched]}
    """
    patch_set = patch.fromfile(patch_file)

    for p in patch_set.items:
        print "patchset diff item (before filter): %s" % (p.target)

    target_files = set()
    target_files.update([os.path.join(solution_path, re.sub(PATH_FIX, '', p.target)) for p in patch_set.items])

    target_files = [p for p in target_files if sub_code_path in p]
    # Add more excluded path here
    target_files = [p for p in target_files if 'tests' not in p]
    target_files = [p for p in target_files if 'docs' not in p]

    target_files = [p for p in target_files if os.path.exists(p)]

    print "patchset diff items set (after filter): %s" % (target_files)

    target_lines = defaultdict(list)

    for p in patch_set.items:
        source_file = os.path.join(solution_path, re.sub(PATH_FIX, '', p.target))
        if source_file not in target_files:
            # skip files filtered out above
            continue
        source_lines = []
        last_hunk_offset = 1
        for hunk in p.hunks:
            patched_lines = []
            line_offset = hunk.starttgt
            for hline in hunk.text:
                if hline.startswith('-'):
                    continue
                if hline.startswith('+'):
                    patched_lines.append(line_offset)
                line_offset += 1
            target_lines[re.sub(PATH_FIX, '', p.target)].extend(patched_lines)
    return target_lines


def generate_css(targets, target_lines):
    coverage_files = os.listdir(coverage_html_dir)

    for target in targets:
        target = re.sub(PATH_FIX, '', target)
        target_name = target.replace('/', '_')
        fname = target_name.replace(".py", ".css")
        html_name = target_name.replace(".py", ".html")
        css = ','.join(["#n%s" %l for l in target_lines[target]])
        css += " {background: red;}"
        css_file = os.path.join(coverage_html_dir, fname)
        with open(css_file, 'w') as f:
            f.write(css)
        html_pattern = re.compile(html_name)
        html_file = [p for p in coverage_files if html_pattern.search(p)]
        if len(html_file) != 1:
            raise ValueError("Found wrong number of matching html files")
        html_file = os.path.join(coverage_html_dir,html_file[0])

        html_source  = open(html_file, 'r').read()
        style_start = html_source.find(current_style)
        new_html = html_source[:style_start]
        new_html += "<link rel='stylesheet' href='%s' type='text/css'>\n" % fname
        new_html += html_source[style_start:]
        os.unlink(html_file)
        with open(html_file, 'w') as f:
            f.write(new_html)


if __name__ == "__main__":
    print "code dir: %s" % (solution_path)
    opt = OptionParser()
    (options, args) = opt.parse_args()
    if not args:
        print "No patch file provided"
        sys.exit(1)
    patchfile = args[0]
    print "patch file: %s" % (patchfile)

    # generate daisy-api coverage reports
    daisy_api_path = os.path.join(solution_path, 'code/daisy/')
    target_lines = parse_patch(patchfile, daisy_api_path)
    print "patch file parse result: %r" % (target_lines)
    daisy_api_raw_result = os.path.join(daisy_api_path, '.coverage')
    print "daisy api coverage raw result file: %s" % (daisy_api_raw_result)
    cov = coverage.coverage(data_file = daisy_api_raw_result)
    cov.load()



    targets = []
    errno = 0

    for t in target_lines.keys():
        path = os.path.join(solution_path, t)
        if not path.endswith('.py'):
            continue
        print "filtered python file to be checked: %s" % (path)

        f, exe, exl, mis, misr = cov.analysis2(path)
        uncovered_in_patch = set(mis) & set(target_lines[t])
        if uncovered_in_patch:
            cover_rate = (len(target_lines[t]) - len(uncovered_in_patch)) * 100 / len(target_lines[t])
            print "cover rate:%d persent" % (cover_rate)  
            targets.append(t)
            target_lines[t] = list(uncovered_in_patch)
            missing_lines = ', '.join([str(x) for x in uncovered_in_patch])
            print '{} missing: {}'.format(t, missing_lines)

            if cover_rate < 90:
                print "cover rate lower than 90!!!!!!!!!"
                errno = 1

    # TODO: make them more useful
    #target_files = [os.path.join(solution_path, x) for x in targets]
    #cov.html_report(morfs=target_files, directory=coverage_html_dir)
    #generate_css(targets, target_lines)

    sys.exit(errno)

