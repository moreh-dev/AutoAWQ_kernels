import os
import sys
from distutils.sysconfig import get_python_lib
from pathlib import Path

import torch
from setuptools import find_packages, setup
from torch.utils.cpp_extension import CUDA_HOME, BuildExtension, CUDAExtension

os.environ["CC"] = "g++"
os.environ["CXX"] = "g++"
AUTOAWQ_KERNELS_VERSION = "0.0.1"

common_setup_kwargs = {
    "version": AUTOAWQ_KERNELS_VERSION,
    "name": "autoawq_kernels",
    "author": "Casper Hansen",
    "license": "MIT",
    "python_requires": ">=3.8.0",
    "description": "AutoAWQ Kernels implements the AWQ kernels.",
    "long_description": (Path(__file__).parent / "README.md").read_text(encoding="UTF-8"),
    "long_description_content_type": "text/markdown",
    "url": "https://github.com/casper-hansen/AutoAWQ_kernels",
    "keywords": ["awq", "autoawq", "quantization", "transformers"],
    "platforms": ["linux", "windows"],
    "classifiers": [
        "Environment :: GPU :: NVIDIA CUDA :: 11.8",
        "Environment :: GPU :: NVIDIA CUDA :: 12",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: C++",
    ]
}


PYPI_BUILD = os.getenv("PYPI_BUILD", "0") == "1"
BUILD_CUDA_EXT = int(os.environ.get('BUILD_CUDA_EXT', '1')) == 1

if not PYPI_BUILD:
    try:
        CUDA_VERSION = "".join(os.environ.get("CUDA_VERSION", torch.version.cuda).split("."))[:3]
        AUTOAWQ_KERNELS_VERSION += f"+cu{CUDA_VERSION}"
    except Exception as ex:
        raise RuntimeError("Your system must have an Nvidia GPU for installing AutoAWQ")

if BUILD_CUDA_EXT:
    try:
        import torch
    except Exception as e:
        print(f"Building cuda extension requires PyTorch (>=1.13.0) being installed, please install PyTorch first: {e}")
        sys.exit(1)

    CUDA_VERSION = None
    ROCM_VERSION = os.environ.get('ROCM_VERSION', None)
    # if ROCM_VERSION and not torch.version.hip:
    #     print(
    #         f"Trying to compile auto-gptq for RoCm, but PyTorch {torch.__version__} "
    #         "is installed without RoCm support."
    #     )
    #     sys.exit(1)

    if not ROCM_VERSION:
        default_cuda_version = torch.version.cuda
        CUDA_VERSION = "".join(os.environ.get("CUDA_VERSION", default_cuda_version).split("."))

    if ROCM_VERSION:
        common_setup_kwargs['version'] += f"+rocm{ROCM_VERSION}"
    else:
        if not CUDA_VERSION:
            print(
                f"Trying to compile auto-gptq for CUDA, but Pytorch {torch.__version__} "
                "is installed without CUDA support."
            )
            sys.exit(1)

        # For the PyPI release, the version is simply x.x.x to comply with PEP 440.
        if not PYPI_BUILD:
            common_setup_kwargs['version'] += f"+cu{CUDA_VERSION}"

requirements = [
    # "torch>=2.0.1",
    "torch==1.13.1",
]

def get_include_dirs():
    include_dirs = []

    if not ROCM_VERSION:
        conda_cuda_include_dir = os.path.join(get_python_lib(), "nvidia/cuda_runtime/include")
        if os.path.isdir(conda_cuda_include_dir):
            include_dirs.append(conda_cuda_include_dir)
        this_dir = os.path.dirname(os.path.abspath(__file__))
        include_dirs.append(this_dir)

    return include_dirs

def get_generator_flag():
    generator_flag = []
    torch_dir = torch.__path__[0]
    if os.path.exists(os.path.join(torch_dir, "include", "ATen", "CUDAGeneratorImpl.h")):
        generator_flag = ["-DOLD_GENERATOR_PATH"]
    
    return generator_flag

def check_dependencies():
    if CUDA_HOME is None:
        raise RuntimeError(
            f"Cannot find CUDA_HOME. CUDA must be available to build the package.")

def get_compute_capabilities():
    # Collect the compute capabilities of all available GPUs.
    for i in range(torch.cuda.device_count()):
        major, minor = torch.cuda.get_device_capability(i)
        cc = major * 10 + minor

        if cc < 75:
            raise RuntimeError("GPUs with compute capability less than 7.5 are not supported.")

    # figure out compute capability
    compute_capabilities = {75, 80, 86, 89, 90}

    capability_flags = []
    if not ROCM_VERSION:
        for cap in compute_capabilities:
            capability_flags += ["-gencode", f"arch=compute_{cap},code=sm_{cap}"]

    return capability_flags

# check_dependencies()
include_dirs = get_include_dirs()
generator_flags = get_generator_flag()
arch_flags = get_compute_capabilities()

if os.name == "nt":
    include_arch = os.getenv("INCLUDE_ARCH", "1") == "1"

    # Relaxed args on Windows
    if include_arch:
        extra_compile_args={"nvcc": arch_flags}
    else:
        extra_compile_args={}
else:
    nvcc_flags = [
        "-O3", 
        "-std=c++17",
        "-DENABLE_BF16",
    ]
    if not ROCM_VERSION:
        nvcc_flags.extend([
            "-U__CUDA_NO_HALF_OPERATORS__",
            "-U__CUDA_NO_HALF_CONVERSIONS__",
            "-U__CUDA_NO_BFLOAT16_OPERATORS__",
            "-U__CUDA_NO_BFLOAT16_CONVERSIONS__",
            "-U__CUDA_NO_BFLOAT162_OPERATORS__",
            "-U__CUDA_NO_BFLOAT162_CONVERSIONS__",
            "--expt-relaxed-constexpr",
            "--expt-extended-lambda",
            "--use_fast_math",
        ])
    else:
        nvcc_flags.extend([
            "-U__HIP_NO_HALF_OPERATORS__",
            "-U__HIP_NO_HALF_CONVERSIONS__",
            "-U__HIP_NO_BFLOAT16_OPERATORS__",
            "-U__HIP_NO_BFLOAT16_CONVERSIONS__",
            "-U__HIP_NO_BFLOAT162_OPERATORS__",
            "-U__HIP_NO_BFLOAT162_CONVERSIONS__",
        ])
    extra_compile_args={
        "cxx": ["-g", "-O3", "-fopenmp", "-lgomp", "-std=c++17", "-DENABLE_BF16"],
        "nvcc": nvcc_flags + arch_flags + generator_flags
    }

extensions = [
    CUDAExtension(
        "awq_ext",
        [
            "awq_ext/pybind_awq.cpp",
            "awq_ext/quantization/gemm_cuda_gen.cu",
            "awq_ext/layernorm/layernorm.cu",
            "awq_ext/position_embedding/pos_encoding_kernels.cu",
            "awq_ext/quantization/gemv_cuda.cu"
        ], extra_compile_args=extra_compile_args
    )
]

if os.name != "nt":
    extensions.append(
        CUDAExtension(
            "awq_ft_ext",
            [
                "awq_ext/pybind_awq_ft.cpp",
                "awq_ext/attention/ft_attention.cpp",
                "awq_ext/attention/decoder_masked_multihead_attention.cu"
            ], extra_compile_args=extra_compile_args
        )
    )

additional_setup_kwargs = {
    "ext_modules": extensions,
    "cmdclass": {'build_ext': BuildExtension}
}

common_setup_kwargs.update(additional_setup_kwargs)

setup(
    packages=find_packages(),
    install_requires=requirements,
    include_dirs=include_dirs,
    **common_setup_kwargs
)
