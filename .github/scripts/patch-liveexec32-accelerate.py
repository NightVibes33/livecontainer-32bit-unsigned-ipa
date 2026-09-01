#!/usr/bin/env python3
"""Implement corpus-required Accelerate routines wholly in guest memory."""
from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/Accelerate/Accelerate.m")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(r'''@import Accelerate;

#include <limits.h>
#include <math.h>
#include <stddef.h>

void vDSP_ctoz(const DSPComplex *input, vDSP_Stride inputStride,
               const DSPSplitComplex *output, vDSP_Stride outputStride,
               vDSP_Length count) {
    if(!input || !output || !output->realp || !output->imagp) return;
    const float *interleaved = (const float *)input;
    for(vDSP_Length index = 0; index < count; ++index) {
        output->realp[index * outputStride] = interleaved[index * inputStride];
        output->imagp[index * outputStride] = interleaved[index * inputStride + 1];
    }
}

void vDSP_ctozD(const DSPDoubleComplex *input, vDSP_Stride inputStride,
                const DSPDoubleSplitComplex *output, vDSP_Stride outputStride,
                vDSP_Length count) {
    if(!input || !output || !output->realp || !output->imagp) return;
    const double *interleaved = (const double *)input;
    for(vDSP_Length index = 0; index < count; ++index) {
        output->realp[index * outputStride] = interleaved[index * inputStride];
        output->imagp[index * outputStride] = interleaved[index * inputStride + 1];
    }
}

void vDSP_ztoc(const DSPSplitComplex *input, vDSP_Stride inputStride,
               DSPComplex *output, vDSP_Stride outputStride,
               vDSP_Length count) {
    if(!input || !input->realp || !input->imagp || !output) return;
    float *interleaved = (float *)output;
    for(vDSP_Length index = 0; index < count; ++index) {
        interleaved[index * outputStride] = input->realp[index * inputStride];
        interleaved[index * outputStride + 1] = input->imagp[index * inputStride];
    }
}

void vDSP_vadd(const float *left, vDSP_Stride leftStride,
               const float *right, vDSP_Stride rightStride,
               float *output, vDSP_Stride outputStride, vDSP_Length count) {
    if(!left || !right || !output) return;
    for(vDSP_Length index = 0; index < count; ++index)
        output[index * outputStride] = left[index * leftStride] + right[index * rightStride];
}

void vDSP_vdistD(const double *real, vDSP_Stride realStride,
                 const double *imaginary, vDSP_Stride imaginaryStride,
                 double *output, vDSP_Stride outputStride, vDSP_Length count) {
    if(!real || !imaginary || !output) return;
    for(vDSP_Length index = 0; index < count; ++index)
        output[index * outputStride] = hypot(real[index * realStride], imaginary[index * imaginaryStride]);
}

void vDSP_vfix16(const float *input, vDSP_Stride inputStride,
                 short *output, vDSP_Stride outputStride, vDSP_Length count) {
    if(!input || !output) return;
    for(vDSP_Length index = 0; index < count; ++index) {
        const float value = input[index * inputStride];
        output[index * outputStride] = isnan(value) ? 0 :
            value >= SHRT_MAX ? SHRT_MAX : value <= SHRT_MIN ? SHRT_MIN : (short)value;
    }
}

void vDSP_vflt16(const short *input, vDSP_Stride inputStride,
                 float *output, vDSP_Stride outputStride, vDSP_Length count) {
    if(!input || !output) return;
    for(vDSP_Length index = 0; index < count; ++index)
        output[index * outputStride] = (float)input[index * inputStride];
}

void vDSP_vmulD(const double *left, vDSP_Stride leftStride,
                const double *right, vDSP_Stride rightStride,
                double *output, vDSP_Stride outputStride, vDSP_Length count) {
    if(!left || !right || !output) return;
    for(vDSP_Length index = 0; index < count; ++index)
        output[index * outputStride] = left[index * leftStride] * right[index * rightStride];
}

void vDSP_vsadd(const float *input, vDSP_Stride inputStride,
                const float *scalar, float *output, vDSP_Stride outputStride,
                vDSP_Length count) {
    if(!input || !scalar || !output) return;
    const float value = *scalar;
    for(vDSP_Length index = 0; index < count; ++index)
        output[index * outputStride] = input[index * inputStride] + value;
}

void vDSP_vsmul(const float *input, vDSP_Stride inputStride,
                const float *scalar, float *output, vDSP_Stride outputStride,
                vDSP_Length count) {
    if(!input || !scalar || !output) return;
    const float value = *scalar;
    for(vDSP_Length index = 0; index < count; ++index)
        output[index * outputStride] = input[index * inputStride] * value;
}

void vDSP_vsmulD(const double *input, vDSP_Stride inputStride,
                 const double *scalar, double *output, vDSP_Stride outputStride,
                 vDSP_Length count) {
    if(!input || !scalar || !output) return;
    const double value = *scalar;
    for(vDSP_Length index = 0; index < count; ++index)
        output[index * outputStride] = input[index * inputStride] * value;
}
''')
print("Accelerate: implemented 11 guest-memory vDSP routines")
