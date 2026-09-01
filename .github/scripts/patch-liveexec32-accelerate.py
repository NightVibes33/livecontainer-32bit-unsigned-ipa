#!/usr/bin/env python3
"""Implement corpus-required Accelerate routines wholly in guest memory."""
from pathlib import Path

path = Path("build/LiveExec32/GuestFrameworks/Accelerate/Accelerate.m")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(r'''#import <Accelerate/Accelerate.h>

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


static int LC32VImageBufferValidARGB8888(const vImage_Buffer *buffer) {
    return buffer && buffer->data && buffer->width <= SIZE_MAX / 4 &&
        buffer->rowBytes >= buffer->width * 4 &&
        (!buffer->height || buffer->rowBytes <= SIZE_MAX / buffer->height);
}

vImage_Error vImageBuffer_Init(vImage_Buffer *buffer,
                               vImagePixelCount height,
                               vImagePixelCount width,
                               uint32_t pixelBits,
                               vImage_Flags flags) {
    const vImage_Flags allowed = kvImageNoAllocate |
        kvImagePrintDiagnosticsToConsole;
    if(!buffer) return kvImageNullPointerArgument;
    memset(buffer, 0, sizeof(*buffer));
    if(flags & ~allowed) return kvImageUnknownFlagsBit;
    if(!pixelBits || width > (SIZE_MAX - 7) / pixelBits)
        return kvImageInvalidParameter;
    const size_t rowBytesUnaligned = ((size_t)width * pixelBits + 7) / 8;
    const size_t alignment = 64;
    if(rowBytesUnaligned > SIZE_MAX - (alignment - 1))
        return kvImageInvalidParameter;
    const size_t rowBytes = (rowBytesUnaligned + alignment - 1) &
        ~(alignment - 1);
    if(height && rowBytes > SIZE_MAX / (size_t)height)
        return kvImageInvalidParameter;
    buffer->height = height;
    buffer->width = width;
    buffer->rowBytes = rowBytes;
    if(flags & kvImageNoAllocate) return (vImage_Error)alignment;
    const size_t bytes = rowBytes * (size_t)height;
    void *data = NULL;
    if(bytes && posix_memalign(&data, alignment, bytes) != 0)
        return kvImageMemoryAllocationError;
    buffer->data = data;
    return kvImageNoError;
}

vImage_Error vImageHistogramCalculation_ARGB8888(
        const vImage_Buffer *source, vImagePixelCount *histogram[4],
        vImage_Flags flags) {
    const vImage_Flags allowed = kvImageLeaveAlphaUnchanged | kvImageDoNotTile;
    if(!LC32VImageBufferValidARGB8888(source) || !histogram)
        return kvImageNullPointerArgument;
    if(flags & ~allowed) return kvImageUnknownFlagsBit;
    const size_t firstChannel = (flags & kvImageLeaveAlphaUnchanged) ? 1 : 0;
    for(size_t channel = firstChannel; channel < 4; ++channel) {
        if(!histogram[channel]) return kvImageNullPointerArgument;
        memset(histogram[channel], 0, 256 * sizeof(*histogram[channel]));
    }
    for(size_t row = 0; row < source->height; ++row) {
        const uint8_t *pixel = (const uint8_t *)source->data +
            row * source->rowBytes;
        for(size_t column = 0; column < source->width; ++column, pixel += 4)
            for(size_t channel = firstChannel; channel < 4; ++channel)
                ++histogram[channel][pixel[channel]];
    }
    return kvImageNoError;
}

static uint8_t LC32VImageClampToByte(int64_t value) {
    return value < 0 ? 0 : value > 255 ? 255 : (uint8_t)value;
}

vImage_Error vImageMatrixMultiply_ARGB8888(
        const vImage_Buffer *source, const vImage_Buffer *destination,
        const int16_t matrix[16], int32_t divisor,
        const int16_t *preBias, const int32_t *postBias,
        vImage_Flags flags) {
    const vImage_Flags allowed = kvImageLeaveAlphaUnchanged | kvImageDoNotTile;
    if(!LC32VImageBufferValidARGB8888(source) ||
       !LC32VImageBufferValidARGB8888(destination) || !matrix)
        return kvImageNullPointerArgument;
    if(flags & ~allowed) return kvImageUnknownFlagsBit;
    if(destination->width > source->width ||
       destination->height > source->height)
        return kvImageRoiLargerThanInputBuffer;
    if(!divisor) divisor = 1;
    for(size_t row = 0; row < destination->height; ++row) {
        const uint8_t *input = (const uint8_t *)source->data +
            row * source->rowBytes;
        uint8_t *output = (uint8_t *)destination->data +
            row * destination->rowBytes;
        for(size_t column = 0; column < destination->width;
            ++column, input += 4, output += 4) {
            uint8_t original[4];
            memcpy(original, input, sizeof(original));
            for(size_t result = 0; result < 4; ++result) {
                if(result == 0 && (flags & kvImageLeaveAlphaUnchanged)) {
                    output[result] = original[result];
                    continue;
                }
                int64_t accumulator = postBias ? postBias[result] : 0;
                for(size_t component = 0; component < 4; ++component) {
                    const int64_t biased = (int64_t)original[component] +
                        (preBias ? preBias[component] : 0);
                    accumulator += biased * matrix[component * 4 + result];
                }
                output[result] = LC32VImageClampToByte(accumulator / divisor);
            }
        }
    }
    return kvImageNoError;
}

vImage_Error vImageBoxConvolve_ARGB8888(
        const vImage_Buffer *source, const vImage_Buffer *destination,
        void *temporaryBuffer, vImagePixelCount sourceOffsetX,
        vImagePixelCount sourceOffsetY, uint32_t kernelHeight,
        uint32_t kernelWidth, const Pixel_8888 backgroundColor,
        vImage_Flags flags) {
    (void)temporaryBuffer;
    const vImage_Flags edgeMask = kvImageCopyInPlace |
        kvImageBackgroundColorFill | kvImageEdgeExtend |
        kvImageTruncateKernel;
    const vImage_Flags allowed = edgeMask | kvImageLeaveAlphaUnchanged |
        kvImageDoNotTile | kvImageGetTempBufferSize;
    if(!LC32VImageBufferValidARGB8888(source) ||
       !LC32VImageBufferValidARGB8888(destination))
        return kvImageNullPointerArgument;
    if(flags & ~allowed) return kvImageUnknownFlagsBit;
    const vImage_Flags edge = flags & edgeMask;
    if(!edge || (edge & (edge - 1))) return kvImageInvalidEdgeStyle;
    if(!kernelHeight || !kernelWidth || !(kernelHeight & 1) ||
       !(kernelWidth & 1)) return kvImageInvalidKernelSize;
    if(sourceOffsetX > source->width ||
       destination->width > source->width - sourceOffsetX)
        return kvImageInvalidOffset_X;
    if(sourceOffsetY > source->height ||
       destination->height > source->height - sourceOffsetY)
        return kvImageInvalidOffset_Y;
    if(edge == kvImageBackgroundColorFill && !backgroundColor)
        return kvImageNullPointerArgument;
    if(flags & kvImageGetTempBufferSize) return 0;
    if(destination->height && destination->rowBytes >
       SIZE_MAX / destination->height) return kvImageInvalidParameter;
    const size_t outputBytes = destination->rowBytes * destination->height;
    uint8_t *result = malloc(outputBytes ? outputBytes : 1);
    if(!result) return kvImageMemoryAllocationError;
    if(outputBytes) memcpy(result, destination->data, outputBytes);
    const int64_t radiusY = kernelHeight / 2;
    const int64_t radiusX = kernelWidth / 2;
    for(size_t row = 0; row < destination->height; ++row) {
        uint8_t *output = result + row * destination->rowBytes;
        const int64_t centerY = (int64_t)sourceOffsetY + row;
        for(size_t column = 0; column < destination->width;
            ++column, output += 4) {
            const int64_t centerX = (int64_t)sourceOffsetX + column;
            uint64_t sums[4] = {0, 0, 0, 0};
            size_t samples = 0;
            int missing = 0;
            for(int64_t ky = -radiusY; ky <= radiusY; ++ky) {
                for(int64_t kx = -radiusX; kx <= radiusX; ++kx) {
                    int64_t y = centerY + ky;
                    int64_t x = centerX + kx;
                    const uint8_t *pixel = NULL;
                    if(x >= 0 && y >= 0 && x < (int64_t)source->width &&
                       y < (int64_t)source->height) {
                        pixel = (const uint8_t *)source->data +
                            (size_t)y * source->rowBytes + (size_t)x * 4;
                    } else if(edge == kvImageEdgeExtend) {
                        if(x < 0) x = 0;
                        else if(x >= (int64_t)source->width)
                            x = (int64_t)source->width - 1;
                        if(y < 0) y = 0;
                        else if(y >= (int64_t)source->height)
                            y = (int64_t)source->height - 1;
                        pixel = (const uint8_t *)source->data +
                            (size_t)y * source->rowBytes + (size_t)x * 4;
                    } else if(edge == kvImageBackgroundColorFill) {
                        pixel = backgroundColor;
                    } else if(edge == kvImageCopyInPlace) {
                        missing = 1;
                        continue;
                    } else {
                        continue;
                    }
                    ++samples;
                    for(size_t channel = 0; channel < 4; ++channel)
                        sums[channel] += pixel[channel];
                }
            }
            const uint8_t *center = (const uint8_t *)source->data +
                (size_t)centerY * source->rowBytes + (size_t)centerX * 4;
            if(missing && edge == kvImageCopyInPlace) {
                memcpy(output, center, 4);
                continue;
            }
            if(!samples) {
                free(result);
                return kvImageInvalidParameter;
            }
            for(size_t channel = 0; channel < 4; ++channel) {
                if(channel == 0 && (flags & kvImageLeaveAlphaUnchanged))
                    output[channel] = center[channel];
                else
                    output[channel] = (uint8_t)((sums[channel] + samples / 2) /
                        samples);
            }
        }
    }
    if(outputBytes) memcpy(destination->data, result, outputBytes);
    free(result);
    return kvImageNoError;
}


static int LC32VImageFormatValid(const vImage_CGImageFormat *format,
                                   int allowDecode) {
    if(!format || format->version > 1 || (!allowDecode && format->decode))
        return 0;
    switch(format->bitsPerComponent) {
        case 1: case 2: case 4: case 5: case 8: case 16: case 32:
            break;
        default:
            return 0;
    }
    return format->bitsPerPixel >= format->bitsPerComponent;
}

vImage_Error vImageBuffer_InitWithCGImage(
        vImage_Buffer *buffer, vImage_CGImageFormat *format,
        const CGFloat *backgroundColor, CGImageRef image,
        vImage_Flags flags) {
    const vImage_Flags allowed = kvImageNoAllocate |
        kvImagePrintDiagnosticsToConsole | kvImageDoNotTile;
    if(!buffer || !format || !image) return kvImageNullPointerArgument;
    if(flags & ~allowed) return kvImageUnknownFlagsBit;
    if(!LC32VImageFormatValid(format, 0)) return kvImageInvalidImageFormat;
    const size_t width = CGImageGetWidth(image);
    const size_t height = CGImageGetHeight(image);
    if(!width || !height) return kvImageInvalidImageObject;
    void *providedData = buffer->data;
    const size_t providedRowBytes = buffer->rowBytes;
    int allocated = 0;
    if(flags & kvImageNoAllocate) {
        if(!providedData || width > (SIZE_MAX - 7) / format->bitsPerPixel)
            return kvImageInvalidParameter;
        const size_t minimumRowBytes =
            (width * format->bitsPerPixel + 7) / 8;
        if(providedRowBytes < minimumRowBytes ||
           (height && providedRowBytes > SIZE_MAX / height))
            return kvImageInvalidRowBytes;
        buffer->data = providedData;
        buffer->width = width;
        buffer->height = height;
        buffer->rowBytes = providedRowBytes;
    } else {
        const vImage_Error result = vImageBuffer_Init(buffer, height, width,
            format->bitsPerPixel, kvImageNoFlags);
        if(result != kvImageNoError) return result;
        allocated = 1;
    }
    CGColorSpaceRef colorSpace = format->colorSpace;
    int releaseColorSpace = 0;
    if(!colorSpace) {
        colorSpace = CGColorSpaceCreateDeviceRGB();
        releaseColorSpace = 1;
    }
    CGContextRef context = colorSpace ? CGBitmapContextCreate(buffer->data,
        width, height, format->bitsPerComponent, buffer->rowBytes, colorSpace,
        format->bitmapInfo) : NULL;
    if(releaseColorSpace && colorSpace) CGColorSpaceRelease(colorSpace);
    if(!context) {
        if(allocated) free(buffer->data);
        buffer->data = NULL;
        return kvImageInvalidImageFormat;
    }
    const CGRect bounds = CGRectMake(0, 0, width, height);
    if(backgroundColor) {
        CGContextSetFillColor(context, backgroundColor);
        CGContextFillRect(context, bounds);
    }
    CGContextDrawImage(context, bounds, image);
    if(CGBitmapContextGetData(context) != buffer->data) {
        CGContextRelease(context);
        if(allocated) free(buffer->data);
        buffer->data = NULL;
        return kvImageInternalError;
    }
    CGContextRelease(context);
    return kvImageNoError;
}

CGImageRef vImageCreateCGImageFromBuffer(
        const vImage_Buffer *buffer, const vImage_CGImageFormat *format,
        void (*callback)(void *userData, void *bufferData), void *userData,
        vImage_Flags flags, vImage_Error *error) {
    const vImage_Flags allowed = kvImageNoAllocate |
        kvImagePrintDiagnosticsToConsole | kvImageHighQualityResampling |
        kvImageDoNotTile;
    if(error) *error = kvImageNoError;
    if(!buffer || !format) {
        if(error) *error = kvImageNullPointerArgument;
        return NULL;
    }
    if(flags & ~allowed) {
        if(error) *error = kvImageUnknownFlagsBit;
        return NULL;
    }
    if(!LC32VImageFormatValid(format, 1) || !buffer->data ||
       buffer->width > (SIZE_MAX - 7) / format->bitsPerPixel) {
        if(error) *error = kvImageInvalidImageFormat;
        return NULL;
    }
    const size_t minimumRowBytes =
        (buffer->width * format->bitsPerPixel + 7) / 8;
    if(buffer->rowBytes < minimumRowBytes ||
       (buffer->height && buffer->rowBytes > SIZE_MAX / buffer->height)) {
        if(error) *error = kvImageInvalidRowBytes;
        return NULL;
    }
    const size_t byteCount = buffer->rowBytes * buffer->height;
    CGDataProviderRef provider = CGDataProviderCreateWithData(NULL,
        buffer->data, byteCount, NULL);
    if(!provider) {
        if(error) *error = kvImageMemoryAllocationError;
        return NULL;
    }
    CGColorSpaceRef colorSpace = format->colorSpace;
    int releaseColorSpace = 0;
    if(!colorSpace) {
        colorSpace = CGColorSpaceCreateDeviceRGB();
        releaseColorSpace = 1;
    }
    CGImageRef image = colorSpace ? CGImageCreate(buffer->width,
        buffer->height, format->bitsPerComponent, format->bitsPerPixel,
        buffer->rowBytes, colorSpace, format->bitmapInfo, provider,
        format->decode, true, format->renderingIntent) : NULL;
    if(releaseColorSpace && colorSpace) CGColorSpaceRelease(colorSpace);
    CGDataProviderRelease(provider);
    if(!image) {
        if(error) *error = kvImageInvalidImageFormat;
        return NULL;
    }
    /* The bridge copies guest pixels before constructing the native provider.
     * Calling the ownership callback before return is explicitly permitted by
     * vImage and prevents native CoreGraphics from retaining an ARM32 pointer. */
    if(flags & kvImageNoAllocate) {
        if(callback) callback(userData, buffer->data);
        else free(buffer->data);
    }
    return image;
}

''')
print("Accelerate: implemented all corpus vDSP, FFT, and vImage exports")
