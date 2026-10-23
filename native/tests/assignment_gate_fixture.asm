; Independent stack-only fixture, not captured game code.
EXTERN WojdFixtureAssignImpl:PROC
PUBLIC WojdFixtureAssignTarget
PUBLIC WojdFixtureAssignmentOrigin
PUBLIC WojdFixtureAssignmentReturn
.code
WojdFixtureAssignTarget PROC FRAME
    push rsi
    .pushreg rsi
    push rdi
    .pushreg rdi
    sub rsp,28h
    .allocstack 28h
    .endprolog
    mov rsi,rdx
    mov rdi,rcx
    nop
    nop
    call WojdFixtureAssignImpl
    add rsp,28h
    pop rdi
    pop rsi
    ret
WojdFixtureAssignTarget ENDP
WojdFixtureAssignmentOrigin PROC FRAME
    sub rsp,28h
    .allocstack 28h
    .endprolog
    call WojdFixtureAssignTarget
WojdFixtureAssignmentReturn LABEL BYTE
    add rsp,28h
    ret
WojdFixtureAssignmentOrigin ENDP
END
