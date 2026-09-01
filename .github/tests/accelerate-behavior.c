#include <Accelerate/Accelerate.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static void require_close(double actual, double expected, double tolerance,
                          const char *label, size_t index) {
    if(fabs(actual - expected) <= tolerance) return;
    fprintf(stderr, "%s[%zu]: got %.12g expected %.12g\n",
        label, index, actual, expected);
    exit(1);
}

static void direct_real_dft(const double *input, size_t count,
                            double *real, double *imaginary) {
    const double pi = 3.14159265358979323846264338327950288;
    for(size_t frequency = 0; frequency < count; ++frequency) {
        real[frequency] = 0;
        imaginary[frequency] = 0;
        for(size_t sample = 0; sample < count; ++sample) {
            const double angle = -2.0 * pi * (double)(sample * frequency) /
                (double)count;
            real[frequency] += input[sample] * cos(angle);
            imaginary[frequency] += input[sample] * sin(angle);
        }
    }
}

static void test_float_fft(void) {
    enum { count = 16, half = count / 2, stride = 2 };
    float input[count];
    float packedReal[half * stride];
    float packedImaginary[half * stride];
    double source[count], expectedReal[count], expectedImaginary[count];
    for(size_t index = 0; index < count; ++index) {
        input[index] = (float)(sin((double)index * .37) + index * .125);
        source[index] = input[index];
    }
    for(size_t index = 0; index < half * stride; ++index)
        packedReal[index] = packedImaginary[index] = -9999;
    for(size_t index = 0; index < half; ++index) {
        packedReal[index * stride] = input[index * 2];
        packedImaginary[index * stride] = input[index * 2 + 1];
    }
    direct_real_dft(source, count, expectedReal, expectedImaginary);
    DSPSplitComplex split = {packedReal, packedImaginary};
    FFTSetup setup = vDSP_create_fftsetup(4, kFFTRadix2);
    if(!setup) exit(2);
    vDSP_fft_zrip(setup, &split, stride, 4, kFFTDirection_Forward);
    require_close(packedReal[0], 2 * expectedReal[0], 1e-4, "float dc", 0);
    require_close(packedImaginary[0], 2 * expectedReal[half], 1e-4,
        "float nyquist", 0);
    for(size_t index = 1; index < half; ++index) {
        require_close(packedReal[index * stride], 2 * expectedReal[index],
            2e-4, "float real", index);
        require_close(packedImaginary[index * stride],
            2 * expectedImaginary[index], 2e-4, "float imag", index);
        require_close(packedReal[index * stride - 1], -9999, 0,
            "float stride real guard", index);
        require_close(packedImaginary[index * stride - 1], -9999, 0,
            "float stride imag guard", index);
    }
    vDSP_fft_zrip(setup, &split, stride, 4, kFFTDirection_Inverse);
    for(size_t index = 0; index < half; ++index) {
        require_close(packedReal[index * stride], 2 * input[index * 2],
            2e-4, "float inverse even", index);
        require_close(packedImaginary[index * stride], 2 * input[index * 2 + 1],
            2e-4, "float inverse odd", index);
    }
    vDSP_destroy_fftsetup(setup);
}

static void test_double_fft(void) {
    enum { count = 8, half = count / 2 };
    double input[count], real[half], imaginary[half];
    double expectedReal[count], expectedImaginary[count];
    for(size_t index = 0; index < count; ++index)
        input[index] = cos((double)index * .23) - index * .0625;
    for(size_t index = 0; index < half; ++index) {
        real[index] = input[index * 2];
        imaginary[index] = input[index * 2 + 1];
    }
    direct_real_dft(input, count, expectedReal, expectedImaginary);
    DSPDoubleSplitComplex split = {real, imaginary};
    FFTSetupD setup = vDSP_create_fftsetupD(3, kFFTRadix5);
    if(!setup) exit(3);
    vDSP_fft_zripD(setup, &split, 1, 3, kFFTDirection_Forward);
    require_close(real[0], 2 * expectedReal[0], 1e-11, "double dc", 0);
    require_close(imaginary[0], 2 * expectedReal[half], 1e-11,
        "double nyquist", 0);
    for(size_t index = 1; index < half; ++index) {
        require_close(real[index], 2 * expectedReal[index], 1e-11,
            "double real", index);
        require_close(imaginary[index], 2 * expectedImaginary[index], 1e-11,
            "double imag", index);
    }
    vDSP_fft_zripD(setup, &split, 1, 3, kFFTDirection_Inverse);
    for(size_t index = 0; index < half; ++index) {
        require_close(real[index], 2 * input[index * 2], 1e-11,
            "double inverse even", index);
        require_close(imaginary[index], 2 * input[index * 2 + 1], 1e-11,
            "double inverse odd", index);
    }
    vDSP_destroy_fftsetupD(setup);
}

static void test_vector_routines(void) {
    const float left[] = {1, 99, -2, 99, 3, 99};
    const float right[] = {4, 99, 5, 99, -6, 99};
    float output[] = {0, 77, 0, 77, 0, 77};
    vDSP_vadd(left, 2, right, 2, output, 2, 3);
    const double expected[] = {5, 3, -3};
    for(size_t index = 0; index < 3; ++index) {
        require_close(output[index * 2], expected[index], 0,
            "vadd", index);
        require_close(output[index * 2 + 1], 77, 0, "vadd guard", index);
    }
    const float scalar = -2;
    vDSP_vsmul(left, 2, &scalar, output, 2, 3);
    require_close(output[0], -2, 0, "vsmul", 0);
    require_close(output[2], 4, 0, "vsmul", 1);
    require_close(output[4], -6, 0, "vsmul", 2);
}

int main(void) {
    test_float_fft();
    test_double_fft();
    test_vector_routines();
    puts("Accelerate compatibility behavior passed");
    return 0;
}
