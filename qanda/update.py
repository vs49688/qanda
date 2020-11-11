#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import sys
import argparse

from . import *

def update():
	ap = argparse.ArgumentParser('qanda')
	ap.add_argument('-s', '--state-file',
		type=str,
		help='state file (default: qanda-state.json)',
		default='qanda-state.json'
	)

	ap.add_argument('outfile', help='output file. use - for stdout. (default: -)', default='-', nargs='?')

	args = ap.parse_args()

	try:
		with open(args.state_file, 'r') as f:
			current = from_json(f)
	except FileNotFoundError:
		current = {}

	print(f'Loaded {len(current)} existing episodes...', file=sys.stderr)

	eps = list(current.values())
	eps.sort(key=lambda x: parse_timestamp(x.time))

	if len(eps) == 0:
		year = 2008
	else:
		year = parse_timestamp(eps[-1].time).year

	# Always scrape ((current_year)) + 1 in case we're in December
	year_eps = {}

	while True:
		print(f'Scraping {year}...', file=sys.stderr)
		size = len(year_eps)
		fetch_year(year, year_eps)
		year += 1

		if len(year_eps) - size == 0:
			break


	diff = {id: year_eps[id] for id in (year_eps.keys() - current.keys())}

	print(f'Found {len(diff)} new episodes...', file=sys.stderr)

	for id, ep in diff.items():
		print(f'  Episode {ep.episode_id} - {ep.title} - {ep.time}', file=sys.stderr)
		ep = fetch_pageinfo(ep)
		ep = get_size(ep)
		current[id] = ep

	if len(diff) == 0:
		print(f'No new episodes, not overwriting state...', file=sys.stderr)
	else:
		print(f'Writing {len(current)} episodes...', file=sys.stderr)
		with open(args.state_file, 'w') as f:
			to_json(current, f)

	print('Regenerating feed...', file=sys.stderr)

	if args.outfile == '-':
		sys.stdout.buffer.write(build_podcast(current.values()))
	else:
		with open(args.outfile, 'wb') as f:
			f.write(build_podcast(current.values()))

	return 0
