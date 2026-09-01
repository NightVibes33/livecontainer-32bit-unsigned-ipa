#!/usr/bin/env python3
"""Implement corpus-required Accelerate routines wholly in guest memory."""
from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/Accelerate/Accelerate.m")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(r'''@import Accelerate;

#include <limits.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

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


typedef struct {
    vDSP_Length maximumLog2;
    FFTRadix radix;
    uint32_t precisionTag;
} LC32FFTSetupState;

enum {
    LC32FFTSetupFloatTag = 0x46333220u,
    LC32FFTSetupDoubleTag = 0x46363420u,
};

static LC32FFTSetupState *LC32CreateFFTSetup(vDSP_Length maximumLog2,
                                              FFTRadix radix,
                                              uint32_t precisionTag) {
    if(maximumLog2 < 1 || maximumLog2 >= 31 ||
       radix < kFFTRadix2 || radix > kFFTRadix5) return NULL;
    LC32FFTSetupState *state = calloc(1, sizeof(*state));
    if(!state) return NULL;
    state->maximumLog2 = maximumLog2;
    state->radix = radix;
    state->precisionTag = precisionTag;
    return state;
}

FFTSetup vDSP_create_fftsetup(vDSP_Length maximumLog2, FFTRadix radix) {
    return (FFTSetup)LC32CreateFFTSetup(maximumLog2, radix,
        LC32FFTSetupFloatTag);
}

FFTSetupD vDSP_create_fftsetupD(vDSP_Length maximumLog2, FFTRadix radix) {
    return (FFTSetupD)LC32CreateFFTSetup(maximumLog2, radix,
        LC32FFTSetupDoubleTag);
}

void vDSP_destroy_fftsetup(FFTSetup setup) {
    free((void *)setup);
}

void vDSP_destroy_fftsetupD(FFTSetupD setup) {
    free((void *)setup);
}

static void LC32FFTDouble(double *real, double *imaginary, size_t count,
                          FFTDirection direction) {
    for(size_t input = 1, reversed = 0; input < count; ++input) {
        size_t bit = count >> 1;
        while(reversed & bit) {
            reversed ^= bit;
            bit >>= 1;
        }
        reversed ^= bit;
        if(input < reversed) {
            double value = real[input];
            real[input] = real[reversed];
            real[reversed] = value;
            value = imaginary[input];
            imaginary[input] = imaginary[reversed];
            imaginary[reversed] = value;
        }
    }

    const double pi = 3.14159265358979323846264338327950288;
    for(size_t length = 2; length <= count; length <<= 1) {
        const double angle = (direction == kFFTDirection_Forward ? -2.0 : 2.0)
            * pi / (double)length;
        const double stepReal = cos(angle);
        const double stepImaginary = sin(angle);
        for(size_t base = 0; base < count; base += length) {
            double twiddleReal = 1.0;
            double twiddleImaginary = 0.0;
            for(size_t offset = 0; offset < length / 2; ++offset) {
                const size_t even = base + offset;
                const size_t odd = even + length / 2;
                const double oddReal = real[odd] * twiddleReal -
                    imaginary[odd] * twiddleImaginary;
                const double oddImaginary = real[odd] * twiddleImaginary +
                    imaginary[odd] * twiddleReal;
                real[odd] = real[even] - oddReal;
                imaginary[odd] = imaginary[even] - oddImaginary;
                real[even] += oddReal;
                imaginary[even] += oddImaginary;
                const double nextReal = twiddleReal * stepReal -
                    twiddleImaginary * stepImaginary;
                twiddleImaginary = twiddleReal * stepImaginary +
                    twiddleImaginary * stepReal;
                twiddleReal = nextReal;
            }
        }
    }

    if(direction == kFFTDirection_Inverse) {
        const double inverseCount = 1.0 / (double)count;
        for(size_t index = 0; index < count; ++index) {
            real[index] *= inverseCount;
            imaginary[index] *= inverseCount;
        }
    }
}

static int LC32ValidateFFTSetup(const LC32FFTSetupState *state,
                                vDSP_Length log2n, uint32_t precisionTag,
                                FFTDirection direction) {
    return state && state->precisionTag == precisionTag && log2n >= 1 &&
        log2n <= state->maximumLog2 && log2n < 31 &&
        (direction == kFFTDirection_Forward ||
         direction == kFFTDirection_Inverse);
}

void vDSP_fft_zrip(FFTSetup setup, const DSPSplitComplex *data,
                   vDSP_Stride stride, vDSP_Length log2n,
                   FFTDirection direction) {
    const LC32FFTSetupState *state = (const LC32FFTSetupState *)setup;
    if(!data || !data->realp || !data->imagp || stride <= 0 ||
       !LC32ValidateFFTSetup(state, log2n, LC32FFTSetupFloatTag, direction))
        return;
    const size_t count = (size_t)1 << log2n;
    const size_t half = count >> 1;
    double *real = calloc(count, sizeof(*real));
    double *imaginary = calloc(count, sizeof(*imaginary));
    if(!real || !imaginary) {
        free(real);
        free(imaginary);
        return;
    }
    if(direction == kFFTDirection_Forward) {
        for(size_t index = 0; index < half; ++index) {
            real[index * 2] = data->realp[index * stride];
            real[index * 2 + 1] = data->imagp[index * stride];
        }
        LC32FFTDouble(real, imaginary, count, direction);
        data->realp[0] = (float)(2.0 * real[0]);
        data->imagp[0] = (float)(2.0 * real[half]);
        for(size_t index = 1; index < half; ++index) {
            data->realp[index * stride] = (float)(2.0 * real[index]);
            data->imagp[index * stride] = (float)(2.0 * imaginary[index]);
        }
    } else {
        real[0] = data->realp[0];
        real[half] = data->imagp[0];
        for(size_t index = 1; index < half; ++index) {
            real[index] = data->realp[index * stride];
            imaginary[index] = data->imagp[index * stride];
            real[count - index] = real[index];
            imaginary[count - index] = -imaginary[index];
        }
        LC32FFTDouble(real, imaginary, count, direction);
        for(size_t index = 0; index < half; ++index) {
            data->realp[index * stride] = (float)real[index * 2];
            data->imagp[index * stride] = (float)real[index * 2 + 1];
        }
    }
    free(real);
    free(imaginary);
}

void vDSP_fft_zripD(FFTSetupD setup, const DSPDoubleSplitComplex *data,
                    vDSP_Stride stride, vDSP_Length log2n,
                    FFTDirection direction) {
    const LC32FFTSetupState *state = (const LC32FFTSetupState *)setup;
    if(!data || !data->realp || !data->imagp || stride <= 0 ||
       !LC32ValidateFFTSetup(state, log2n, LC32FFTSetupDoubleTag, direction))
        return;
    const size_t count = (size_t)1 << log2n;
    const size_t half = count >> 1;
    double *real = calloc(count, sizeof(*real));
    double *imaginary = calloc(count, sizeof(*imaginary));
    if(!real || !imaginary) {
        free(real);
        free(imaginary);
        return;
    }
    if(direction == kFFTDirection_Forward) {
        for(size_t index = 0; index < half; ++index) {
            real[index * 2] = data->realp[index * stride];
            real[index * 2 + 1] = data->imagp[index * stride];
        }
        LC32FFTDouble(real, imaginary, count, direction);
        data->realp[0] = 2.0 * real[0];
        data->imagp[0] = 2.0 * real[half];
        for(size_t index = 1; index < half; ++index) {
            data->realp[index * stride] = 2.0 * real[index];
            data->imagp[index * stride] = 2.0 * imaginary[index];
        }
    } else {
        real[0] = data->realp[0];
        real[half] = data->imagp[0];
        for(size_t index = 1; index < half; ++index) {
            real[index] = data->realp[index * stride];
            imaginary[index] = data->imagp[index * stride];
            real[count - index] = real[index];
            imaginary[count - index] = -imaginary[index];
        }
        LC32FFTDouble(real, imaginary, count, direction);
        for(size_t index = 0; index < half; ++index) {
            data->realp[index * stride] = real[index * 2];
            data->imagp[index * stride] = real[index * 2 + 1];
        }
    }
    free(real);
    free(imaginary);
}

''')
print("Accelerate: implemented guest-memory vDSP and packed-real FFT routines")
