C     Combined dispatcher VUMAT for jobs that use BOTH the truss and beam
C     fiber materials in the same analysis.
C
C     Abaqus/Explicit links exactly one user subroutine file per job
C     (`abaqus ... user=<file>`), and a job may only define SUBROUTINE
C     VUMAT once. VUMAT_truss.for and VUMAT_beam.for are each a complete,
C     standalone VUMAT (for jobs that only ever use one fiber material
C     type) and are kept separate as the two deliverables the goal asked
C     for. This file exists ONLY for a job that embeds both truss and beam
C     fibers at once (the 1-element/4-fiber VUEL smoke test) and dispatches
C     on `cmname` to whichever body applies -- it is not a third
C     independent material model, just the two above pasted under one
C     SUBROUTINE VUMAT so Abaqus can link them together.
C
C     Material names expected (set via *Material, name=... in the deck):
C       TRUSSFIBER -> VUMAT_truss.for's rule (PROPS: EMOD, SFAIL)
C       BEAMFIBER  -> VUMAT_beam.for's rule  (PROPS: EMOD, GMOD, SFAIL)
C     Any other cmname is a hard error (STOP) rather than a silent no-op,
C     so a material-name typo in the deck cannot pass silently.
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
      ncomp=ndir+nshr
      IF (cmname(1:10).EQ.'TRUSSFIBER') THEN
        EMOD=props(1)
        SFAIL=props(2)
        DO k=1,nblock
          DO i=1,ncomp
            stressNew(k,i)=stressOld(k,i)
          END DO
          IF (nstatev.GE.1) stateNew(k,1)=stateOld(k,1)
          IF (nstatev.GE.1 .AND. totalTime.EQ.0.0D0) stateNew(k,1)=1.0D0
          IF (nstatev.GE.1 .AND. stateOld(k,1).EQ.0.0D0
     1        .AND. totalTime.GT.0.0D0) THEN
            DO i=1,ncomp
              stressNew(k,i)=0.0D0
            END DO
          ELSE
            TRIAL=stressOld(k,1)+EMOD*strainInc(k,1)
            IF (TRIAL.LE.0.0D0) THEN
              stressNew(k,1)=RESSTIFF*EMOD*strainInc(k,1)
              IF (stressNew(k,1).GT.0.0D0) stressNew(k,1)=0.0D0
            ELSE IF (TRIAL.GE.SFAIL) THEN
              stressNew(k,1)=0.0D0
              IF (nstatev.GE.1) stateNew(k,1)=0.0D0
            ELSE
              stressNew(k,1)=TRIAL
            END IF
            DO i=2,ncomp
              stressNew(k,i)=0.0D0
            END DO
          END IF
        END DO
      ELSE IF (cmname(1:9).EQ.'BEAMFIBER') THEN
        EMOD=props(1)
        GMOD=props(2)
        SFAIL=props(3)
        DO k=1,nblock
          DO i=1,ncomp
            stressNew(k,i)=stressOld(k,i)
          END DO
          IF (nstatev.GE.1) stateNew(k,1)=stateOld(k,1)
          IF (nstatev.GE.1 .AND. totalTime.EQ.0.0D0) stateNew(k,1)=1.0D0
          IF (nstatev.GE.1 .AND. stateOld(k,1).EQ.0.0D0
     1        .AND. totalTime.GT.0.0D0) THEN
            DO i=1,ncomp
              stressNew(k,i)=0.0D0
            END DO
          ELSE
            TRIAL=stressOld(k,1)+EMOD*strainInc(k,1)
            IF (TRIAL.LE.0.0D0) THEN
              stressNew(k,1)=RESSTIFF*EMOD*strainInc(k,1)
              IF (stressNew(k,1).GT.0.0D0) stressNew(k,1)=0.0D0
            ELSE IF (TRIAL.GE.SFAIL) THEN
              DO i=1,ncomp
                stressNew(k,i)=0.0D0
              END DO
              IF (nstatev.GE.1) stateNew(k,1)=0.0D0
              GOTO 20
            ELSE
              stressNew(k,1)=TRIAL
            END IF
            IF (ncomp.GE.2) THEN
              stressNew(k,2)=stressOld(k,2)+GMOD*strainInc(k,2)
            END IF
            DO i=3,ncomp
              stressNew(k,i)=RESSTIFF*EMOD*strainInc(k,i)
            END DO
   20       CONTINUE
          END IF
        END DO
      ELSE
        WRITE(*,*) '*** VUMAT_fibers_combined: unknown cmname ', cmname
        STOP
      END IF
      RETURN
      END
