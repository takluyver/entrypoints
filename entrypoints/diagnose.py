from collections import defaultdict
import sys

from .reader import EntryPointsScanner

def show_sys_path():
    print(len(sys.path), "locations on sys.path:")
    for path in sys.path:
        if path == '':
            print(" - ''  (cwd)")
        else:
            print(" -", path)
    print()

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

def check_cache_validity():
    with_cache = EntryPointsScanner()
    if not with_cache.user_cache:
        print("No cached data to check.")
        return

    without_cache = EntryPointsScanner(cache_file='')
    cache_valid = True
    needs_manual_refresh = False

    for path, cache_data in with_cache.user_cache.items():
        scan_data = without_cache.entrypoints_for_path(path)
        if scan_data['distributions'] == cache_data['distributions']:
            continue   # Cache is correct

        cache_valid = False
        if path.endswith('.egg') or (cache_data['mtime'] == scan_data['mtime']):
            needs_manual_refresh = True
            print("Cache for {} is invalid".format(path))
        else:
            print("Cache for {} is outdated".format(path))

    if needs_manual_refresh:
        print("Problems with cached data require manual intervention!")
    elif not cache_valid:
        print("Cache outdated; this should be corrected automatically.")
    else:
        print("Data in cache is up to date.")

if __name__ == '__main__':
    show_sys_path()
    check_shadowing()
    check_cache_validity()
