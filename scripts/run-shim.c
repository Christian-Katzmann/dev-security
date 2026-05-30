#include <libgen.h>
#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(void) {
    char executable_path[PATH_MAX];
    uint32_t size = sizeof(executable_path);

    if (_NSGetExecutablePath(executable_path, &size) != 0) {
        fprintf(stderr, "Executable path is too long.\n");
        return 1;
    }

    char resolved_path[PATH_MAX];
    if (realpath(executable_path, resolved_path) == NULL) {
        perror("realpath");
        return 1;
    }

    char dir_buffer[PATH_MAX];
    strncpy(dir_buffer, resolved_path, sizeof(dir_buffer));
    dir_buffer[sizeof(dir_buffer) - 1] = '\0';

    char script_path[PATH_MAX];
    int written = snprintf(script_path, sizeof(script_path), "%s/run.sh", dirname(dir_buffer));
    if (written < 0 || written >= (int)sizeof(script_path)) {
        fprintf(stderr, "Launcher script path is too long.\n");
        return 1;
    }

    execl("/bin/bash", "bash", script_path, (char *)NULL);
    perror("execl");
    return 1;
}
