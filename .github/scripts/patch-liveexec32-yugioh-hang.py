#!/usr/bin/env python3
from pathlib import Path

psynch = Path("build/LiveExec32/HostFrameworks/LC32/dynarmic_psynch.cpp")
s = psynch.read_text()

old = r'''        } else {
            waiter->condition.wait(lock, wakePredicate);
        }
'''
new = r'''        } else if (kind == GuestThreadWaitKind::Mutex) {
            const bool observed = waiter->condition.wait_for(
                lock, std::chrono::seconds(2), wakePredicate);
            if (!observed && !waiter->signaled) {
                size_t sameAddressWaiters = 0;
                for (const auto &candidate : nativeGuestWaiters) {
                    if (!candidate->signaled &&
                            candidate->kind == GuestThreadWaitKind::Mutex &&
                            candidate->address == address) {
                        ++sameAddressWaiters;
                    }
                }
                const u32 pc = threadHandle.jit != nullptr
                    ? threadHandle.jit->Regs()[Reg::PC] : 0;
                const u32 lr = threadHandle.jit != nullptr
                    ? threadHandle.jit->Regs()[Reg::LR] : 0;
                fprintf(stderr,
                    "LC32-YGO-HANG mutex-wait>2s tid=%llu addr=%08x "
                    "seq=%08x firstfit=%d peers=%zu pc=%08x lr=%08x\n",
                    static_cast<unsigned long long>(CurrentGuestThreadId()),
                    address, mutexSequence, mutexFirstFit ? 1 : 0,
                    sameAddressWaiters, pc, lr);
                fflush(stderr);
                continue;
            }
        } else {
            waiter->condition.wait(lock, wakePredicate);
        }
'''
if old not in s:
    raise SystemExit("mutex timed-wait diagnostic anchor missing")
s = s.replace(old, new, 1)

old = r'''        if (woken == 0) {
            RecordGuestMutexPrepost(mutex, targetSequence);
        }
'''
new = r'''        if (woken == 0) {
            RecordGuestMutexPrepost(mutex, targetSequence);
            fprintf(stderr,
                "LC32-YGO-HANG mutex-prepost tid=%llu addr=%08x "
                "target=%08x mgen=%08x ugen=%08x flags=%08x\n",
                static_cast<unsigned long long>(CurrentGuestThreadId()),
                mutex, targetSequence, mgen, ugen, flags);
            fflush(stderr);
        }
'''
if old not in s:
    raise SystemExit("mutex prepost diagnostic anchor missing")
s = s.replace(old, new, 1)
psynch.write_text(s)

native = Path("build/LiveExec32/HostFrameworks/LC32/dynarmic_native_jit.cpp")
s = native.read_text()

old = r'''        nativeGuestJitCondition.wait(lock, [runtime] {
            return runtime->threadStateUsers == 0;
        });
'''
new = r'''        while (runtime->threadStateUsers != 0) {
            if (nativeGuestJitCondition.wait_for(
                    lock, std::chrono::seconds(2)) ==
                    std::cv_status::timeout &&
                    runtime->threadStateUsers != 0) {
                fprintf(stderr,
                    "LC32-YGO-HANG jit-destroy-wait>2s guest-thread=%llu "
                    "users=%zu processor=%zu\n",
                    static_cast<unsigned long long>(runtime->debuggerId),
                    runtime->threadStateUsers, runtime->processorId);
                fflush(stderr);
            }
        }
'''
if old not in s:
    raise SystemExit("JIT teardown wait diagnostic anchor missing")
s = s.replace(old, new, 1)

old = r'''    runtime->hostMachThread =
        pthread_mach_thread_np(pthread_self());

    LC32_DEBUG_FPRINTF(stderr,
'''
new = r'''    runtime->hostMachThread =
        pthread_mach_thread_np(pthread_self());
    fprintf(stderr,
        "LC32-YGO-HANG worker-start guest-thread=%llu host-thread=0x%x "
        "processor=%zu pc=%08x\n",
        static_cast<unsigned long long>(start->debuggerId),
        runtime->hostMachThread, runtime->processorId,
        runtime->jit != nullptr ? runtime->jit->Regs()[Reg::PC] : 0);
    fflush(stderr);

    LC32_DEBUG_FPRINTF(stderr,
'''
if old not in s:
    raise SystemExit("worker-start diagnostic anchor missing")
s = s.replace(old, new, 1)

old = r'''    const auto signalJoinSemaphore = [](
            mach_port_t semaphore, gdb_thread_id_t debuggerId) {
        if (!MACH_PORT_VALID(semaphore)) {
            return;
        }
        const kern_return_t result =
            semaphore_signal_trap(semaphore);
'''
new = r'''    const auto signalJoinSemaphore = [](
            mach_port_t semaphore, gdb_thread_id_t debuggerId) {
        if (!MACH_PORT_VALID(semaphore)) {
            fprintf(stderr,
                "LC32-YGO-HANG join-signal-skip guest-thread=%llu semaphore=null\n",
                static_cast<unsigned long long>(debuggerId));
            fflush(stderr);
            return;
        }
        fprintf(stderr,
            "LC32-YGO-HANG join-signal guest-thread=%llu semaphore=0x%x\n",
            static_cast<unsigned long long>(debuggerId), semaphore);
        fflush(stderr);
        const kern_return_t result =
            semaphore_signal_trap(semaphore);
'''
if old not in s:
    raise SystemExit("join-signal diagnostic anchor missing")
s = s.replace(old, new, 1)

old = r'''        if (detachResult == 0) {
            const mach_port_t joinSemaphore = runtime->joinSemaphore;
            const gdb_thread_id_t debuggerId = runtime->debuggerId;
            runtime->joinSemaphore = MACH_PORT_NULL;
            runtime->hostThreadCreated = false;
            DestroyNativeGuestJit(runtime);
            signalJoinSemaphore(joinSemaphore, debuggerId);
            return nullptr;
        }
'''
new = r'''        if (detachResult == 0) {
            const mach_port_t joinSemaphore = runtime->joinSemaphore;
            const gdb_thread_id_t debuggerId = runtime->debuggerId;
            const auto teardownStarted = std::chrono::steady_clock::now();
            fprintf(stderr,
                "LC32-YGO-HANG jit-destroy-begin guest-thread=%llu "
                "semaphore=0x%x\n",
                static_cast<unsigned long long>(debuggerId), joinSemaphore);
            fflush(stderr);
            runtime->joinSemaphore = MACH_PORT_NULL;
            runtime->hostThreadCreated = false;
            DestroyNativeGuestJit(runtime);
            const auto teardownMs = std::chrono::duration_cast<
                std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - teardownStarted).count();
            fprintf(stderr,
                "LC32-YGO-HANG jit-destroy-end guest-thread=%llu ms=%lld\n",
                static_cast<unsigned long long>(debuggerId),
                static_cast<long long>(teardownMs));
            fflush(stderr);
            signalJoinSemaphore(joinSemaphore, debuggerId);
            return nullptr;
        }
'''
if old not in s:
    raise SystemExit("self teardown diagnostic anchor missing")
s = s.replace(old, new, 1)

old = r'''    const bool nativeThread =
        NativeGuestThreadIsCurrent();
    if (MACH_PORT_VALID(joinSemaphore) &&
'''
new = r'''    const bool nativeThread =
        NativeGuestThreadIsCurrent();
    fprintf(stderr,
        "LC32-YGO-HANG bsdthread-terminate guest-thread=%llu native=%d "
        "join=0x%x free=%08x+%08x\n",
        static_cast<unsigned long long>(currentThreadId),
        nativeThread ? 1 : 0, joinSemaphore, freeAddress, freeSize);
    fflush(stderr);
    if (MACH_PORT_VALID(joinSemaphore) &&
'''
if old not in s:
    raise SystemExit("bsdthread terminate diagnostic anchor missing")
s = s.replace(old, new, 1)

native.write_text(s)
print("LC32: installed Yu-Gi-Oh mutex/join/JIT hang telemetry")
