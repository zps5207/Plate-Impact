C     Abaqus/Explicit elastic-brittle VUMAT for the T3D2 truss fiber.
C
C     Tension-only: an axial trial stress that is non-positive is treated
C     as slack (near-zero stiffness) rather than carrying compression.
C     Tension is linearly elastic up to PROPS(2); crossing that failure
C     stress deletes the material point (STATEV(1)=0) and its stress goes
C     to zero for the remainder of the analysis.  This is intentionally a
C     single-shot brittle rule -- a FUTURE VERSION will replace the
C     instantaneous deletion with a tracked damage variable (progressive
C     stiffness loss vs. the current all-or-nothing STATEV(1) flag).
C
C     A T3D2 truss carries only one stress component (ndir=1, nshr=0), so
C     "discard shear" is structurally already true for this element; any
C     nshr components that a generalized caller still passes in are zeroed
C     defensively below rather than assumed absent.
C
C     RESSTIFF below is a deliberate numerical regularization, not a
C     physical property: Abaqus/Explicit's packager probes a VUMAT for an
C     initial stiffness estimate before increment 1 to size the stable
C     time increment. A truly zero-stiffness compression branch makes that
C     probe fail with "zero or negative initial dilatational modulus"
C     (confirmed against real Abaqus 2024 on this project's tension-only
C     pilot VUMAT; see docs/BUGS.md BUG-016). Clamping compression to a
C     small positive fraction of PROPS(1) instead of exactly zero gives the
C     probe a nonzero slope to find while remaining physically negligible
C     in the tension-dominated regime this element is meant for.
C     THIS FIX IS NOT YET CONFIRMED ON REAL ABAQUS -- BUG-016 was found by
C     an actual ROAR run and no replacement fix has been run there yet;
C     treat RESSTIFF as a candidate mitigation until that run happens.
C
C     PROPS(1) = EMOD  (axial Young's modulus, Pa)      -- 100.0D9 per spec
C     PROPS(2) = SFAIL (axial tensile failure stress, Pa)
C     STATEV(1) = delete flag (1 = active, 0 = deleted)
      SUBROUTINE VUMAT(nblock,ndir,nshr,nstatev,nfieldv,nprops,lanneal,
     1 stepTime,totalTime,dt,cmname,coordMp,charLength,props,density,
     2 strainInc,relSpinInc,tempOld,stretchOld,defgradOld,fieldOld,
     3 stressOld,stateOld, enerInternOld,enerInelasOld,tempNew,
     4 stretchNew,defgradNew,fieldNew,stressNew,stateNew,
     5 enerInternNew,enerInelasNew)
      INCLUDE 'vaba_param.inc'
      CHARACTER*80 cmname
      DIMENSION props(nprops),density(nblock),coordMp(nblock,*),
     1 charLength(nblock),strainInc(nblock,ndir+nshr),
     2 relSpinInc(nblock,nshr),tempOld(nblock),stretchOld(nblock,*),
     3 defgradOld(nblock,*),fieldOld(nblock,nfieldv),
     4 stressOld(nblock,ndir+nshr),stateOld(nblock,nstatev),
     5 enerInternOld(nblock),enerInelasOld(nblock),tempNew(nblock),
     6 stretchNew(nblock,*),defgradNew(nblock,*),fieldNew(nblock,nfieldv),
     7 stressNew(nblock,ndir+nshr),stateNew(nblock,nstatev),
     8 enerInternNew(nblock),enerInelasNew(nblock)
      REAL*8 EMOD,SFAIL,TRIAL,RESSTIFF
      PARAMETER (RESSTIFF=1.0D-4)
      INTEGER k,i
      EMOD=props(1)
      SFAIL=props(2)
      DO k=1,nblock
        DO i=1,ndir+nshr
          stressNew(k,i)=stressOld(k,i)
        END DO
        IF (nstatev.GE.1) stateNew(k,1)=stateOld(k,1)
        IF (nstatev.GE.1 .AND. totalTime.EQ.0.0D0) stateNew(k,1)=1.0D0
        IF (nstatev.GE.1 .AND. stateOld(k,1).EQ.0.0D0
     1      .AND. totalTime.GT.0.0D0) THEN
          DO i=1,ndir+nshr
            stressNew(k,i)=0.0D0
          END DO
        ELSE
          TRIAL=stressOld(k,1)+EMOD*strainInc(k,1)
          IF (TRIAL.LE.0.0D0) THEN
C           Slack in compression: tiny residual stiffness only (see
C           RESSTIFF note above), not true load-carrying compression.
            stressNew(k,1)=RESSTIFF*EMOD*strainInc(k,1)
            IF (stressNew(k,1).GT.0.0D0) stressNew(k,1)=0.0D0
          ELSE IF (TRIAL.GE.SFAIL) THEN
            stressNew(k,1)=0.0D0
            IF (nstatev.GE.1) stateNew(k,1)=0.0D0
          ELSE
            stressNew(k,1)=TRIAL
          END IF
C         Discard shear: a T3D2 truss has none (nshr=0); zero defensively
C         if a caller still supplies extra components.
          DO i=2,ndir+nshr
            stressNew(k,i)=0.0D0
          END DO
        END IF
      END DO
      RETURN
      END
