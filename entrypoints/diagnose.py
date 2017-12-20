from collections import defaultdict
import sys

from .reader import EntryPointsScanner

def check_shadowing():
    scanner = EntryPointsScanner()
    distros_by_name = defaultdict(list)
    any_shadowed = False

    for path in sys.path:
        locn_ep = scanner.entrypoints_for_path(path)
        for distro in locn_ep['distributions']:
            distros_by_name[distro['name']].append((path, distro))

    for distro_name, found in distros_by_name.items():
        if len(found) > 1:
            any_shadowed = True
            print("Multiple installations of {!r}:".format(distro_name))
            visible_path, visible_distro = found[0]
            print(" * {} in {}".format(visible_distro['version'], visible_path))
            for path, distro in found[1:]:
                print("   {} in {}".format(distro['version'], path))
            print()

    if not any_shadowed:
        print("No conflicting distributions found.")

if __name__ == '__main__':
    check_shadowing()
