/**
 ******************************************************************************
 * @file      syscalls.c
 * @brief     STM32CubeIDE System Call stubs (newlib-nano)
 *
 *            Provides minimal stubs for syscalls referenced by libc_nano.
 *            Without these, the linker emits "X is not implemented and will
 *            always fail" warnings which Eclipse counts as build errors.
 ******************************************************************************
 */

#include <errno.h>
#include <sys/stat.h>

int _close(int fd)        { (void)fd; errno = ENOSYS; return -1; }
int _fstat(int fd, struct stat *st) { (void)fd; (void)st; errno = ENOSYS; return -1; }
int _getpid(void)         { return 1; }
int _isatty(int fd)       { (void)fd; return 1; }
int _kill(int pid, int sig) { (void)pid; (void)sig; errno = EINVAL; return -1; }
int _lseek(int fd, int ptr, int dir) { (void)fd; (void)ptr; (void)dir; errno = ENOSYS; return -1; }
int _read(int fd, char *ptr, int len) { (void)fd; (void)ptr; (void)len; errno = ENOSYS; return -1; }
