import os

# keep numerical libraries within the 6-core FEA budget when the package is imported first
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "6")
