C     Abaqus/Explicit elastic-brittle VUMAT for the B31 beam fiber.
C
C     Per the goal decision recorded 2026-09-29 (docs/BUGS.md / progress
C     report), this targets Abaqus/Explicit's native B31 beam (linear,
C     shear-flexible/Timoshenko) rather than a true Euler-Bernoulli beam:
C     Abaqus/Explicit has no B33-equivalent, and VUMAT is not in Abaqus's
C     documented list of user-material-capable element types for beams in
C     the first place (continuum/shell/membrane/truss are listed; beam is
C     not) -- this file is a best-effort application of the truss VUMAT's
C     pattern to a beam section point, NOT a confirmed-supported usage.
C     UNVERIFIED ON REAL ABAQUS: whether Abaqus/Explicit calls this VUMAT
C     at all for a B31 element, and if so, exactly which strain components
C     strainInc(k,:) holds at a beam section point, are both open questions
C     that only an actual ROAR run can settle (same class of finding as
C     BUG-016, which was only discovered by running real Abaqus). This
C     file documents its own assumed component layout below so that a real
C     run's behavior can be diffed against it directly.
C
C     ASSUMED strainInc/stress layout at a beam section point (matching
C     this project's local oracle, which deliberately avoids asserting a
C     real Abaqus convention -- see
C     agents/refiner/outbox/vumat_local_validation/validate_vumat.py):
C       component 1 = axial strain/stress   (tension-only, elastic-brittle)
C       component 2 = transverse shear strain/stress (elastic, G*gamma)
C       any further components (bending/curvature-carried terms, if
C         Abaqus passes any to a user material at all) = suppressed to
C         (near) zero in BOTH signs, since the goal requires no bending
C         response from this material regardless of load direction.
C
C     Tension and shear are both elastic-brittle: linear up to failure,
C     then STATEV(1)=0 deletes the whole section point (all components ->
C     0) for the rest of the analysis. A FUTURE VERSION will replace this
C     instantaneous deletion with a tracked damage variable.
C
C     RESSTIFF is the same non-physical regularization used in
C     VUMAT_truss.for, applied here to both the suppressed-compression and
C     suppressed-bending branches, so Abaqus's pre-increment-1 stiffness
C     probe (BUG-016) does not see an exact zero. NOT YET CONFIRMED against
C     a real Abaqus run.
C
C     PROPS(1) = EMOD  (axial Young's modulus, Pa)        -- 100.0D9
C     PROPS(2) = GMOD  (shear modulus, Pa)                -- 50.0D9
C     PROPS(3) = SFAIL (axial tensile failure stress, Pa)
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
      REAL*8 EMOD,GMOD,SFAIL,TRIAL,RESSTIFF
      PARAMETER (RESSTIFF=1.0D-4)
      INTEGER k,i,ncomp
      EMOD=props(1)
      GMOD=props(2)
      SFAIL=props(3)
      ncomp=ndir+nshr
      DO k=1,nblock
        DO i=1,ncomp
          stressNew(k,i)=stressOld(k,i)
        END DO
        IF (nstatev.GE.1) stateNew(k,1)=stateOld(k,1)
        IF (nstatev.GE.1 .AND. totalTime.EQ.0.0D0) stateNew(k,1)=1.0D0
        IF (nstatev.GE.1 .AND. stateOld(k,1).EQ.0.0D0
     1      .AND. totalTime.GT.0.0D0) THEN
          DO i=1,ncomp
            stressNew(k,i)=0.0D0
          END DO
        ELSE
C         Component 1: axial, tension-only elastic-brittle (same rule as
C         VUMAT_truss.for).
          TRIAL=stressOld(k,1)+EMOD*strainInc(k,1)
          IF (TRIAL.LE.0.0D0) THEN
            stressNew(k,1)=RESSTIFF*EMOD*strainInc(k,1)
            IF (stressNew(k,1).GT.0.0D0) stressNew(k,1)=0.0D0
          ELSE IF (TRIAL.GE.SFAIL) THEN
C           Failure detected THIS increment: zero every component right
C           away (not just the axial one) so a just-broken fiber does not
C           carry a leftover increment of shear before STATEV(1)=0 takes
C           effect on the next call.
            DO i=1,ncomp
              stressNew(k,i)=0.0D0
            END DO
            IF (nstatev.GE.1) stateNew(k,1)=0.0D0
            GOTO 10
          ELSE
            stressNew(k,1)=TRIAL
          END IF
C         Component 2 (if present): transverse shear, fully elastic, no
C         failure rule of its own -- carried until the axial rule deletes
C         the whole point.
          IF (ncomp.GE.2) THEN
            stressNew(k,2)=stressOld(k,2)+GMOD*strainInc(k,2)
          END IF
C         Any remaining components: bending/curvature-carried terms --
C         suppressed in both signs (no bending), with the same
C         RESSTIFF regularization as the compression branch above.
          DO i=3,ncomp
            stressNew(k,i)=RESSTIFF*EMOD*strainInc(k,i)
          END DO
   10     CONTINUE
        END IF
      END DO
      RETURN
      END
