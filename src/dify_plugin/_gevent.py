from gevent import monkey

# Keep the package-level gevent patch as the first import side effect.
monkey.patch_all(sys=True)
