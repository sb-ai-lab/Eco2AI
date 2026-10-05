def resource_filename(package, name):
    """Filesystem path for a package data file.

    importlib.resources is used on Python 3.9+. Python 3.7 keeps pkg_resources
    and closes the stream so Windows can open the same file for writing.
    """
    try:
        from importlib.resources import files
    except ImportError:
        files = None
    if files is not None:
        return str(files(package).joinpath(name))
    from pkg_resources import resource_stream

    stream = resource_stream(package, name)
    try:
        return stream.name
    finally:
        stream.close()
