# AutoAWQ Kernels

AutoAWQ Kernels is a new package that is split up from the [main repository](https://github.com/casper-hansen/AutoAWQ) in order to avoid compilation times.

## Requirements

- Windows: Must use WSL2.
- GPU: Must be compute capability 7.5 or higher.
- CUDA Toolkit: Must be 11.8 or higher.

## Install

### Install from PyPi

```
pip install autoawq-kernels
```

### Build from source
In [torch/utils/cpp_extension.py](https://github.com/pytorch/pytorch/blob/ad507789d12e3f757a43f35cd66e7aea6124140d/torch/utils/cpp_extension.py#L209), set the following:
```python
IS_HIP_EXTENSION = True
ROCM_VERSION = (5,3)
```

```
git clone https://github.com/casper-hansen/AutoAWQ_kernels
cd AutoAWQ_kernels
ROCM_VERSION=5.3.3 \
ROCM_HOME=/opt/rocm \
PYTORCH_ROCM_ARCH=gfx90a \
pip install -e .
```
