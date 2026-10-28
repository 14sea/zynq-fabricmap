/* No product source edit. Include original app to expose its counter to this boundary fixture.
 * Linker wrapping sets only sequence state just before the original P4 event emitter runs. */
#include <stdlib.h>
#include <string.h>
#include "b4q_app.c"
void __real_b4q_emit(const char *line);
void __wrap_b4q_emit(const char *line);
void __wrap_b4q_emit(const char *line)
{
 static int cut;
 if (!cut && getenv("B4Q_OWNER_CUT") && strncmp(line,"EV P4 ",6)==0) { S.seq=B4Q_APP_SEQ_LIMIT;cut=1; }
 __real_b4q_emit(line);
}
