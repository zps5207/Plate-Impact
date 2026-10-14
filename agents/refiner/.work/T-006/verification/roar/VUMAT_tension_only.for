C     Abaqus/Explicit tension-only elastic-brittle VUMAT.
C     PROPS(1)=Young modulus; PROPS(2)=failure stress; density is *Density.
C     STATEV(1)=delete flag (1 = active, 0 = deleted). Compression is clamped.
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
      REAL*8 EFAIL,EMOD,TRIAL
      INTEGER k,i
      EMOD=props(1)
      EFAIL=props(2)
      DO k=1,nblock
        DO i=1,ndir+nshr
          stressNew(k,i)=stressOld(k,i)
        END DO
        IF (nstatev.GE.1) stateNew(k,1)=stateOld(k,1)
        IF (nstatev.GE.1 .AND. totalTime.EQ.0.0D0) stateNew(k,1)=1.0D0
        IF (nstatev.GE.1 .AND. stateOld(k,1).EQ.0.0D0 .AND. totalTime.GT.0.0D0) THEN
          DO i=1,ndir+nshr
            stressNew(k,i)=0.0D0
          END DO
        ELSE
          TRIAL=stressOld(k,1)+EMOD*strainInc(k,1)
          IF (TRIAL.LE.0.0D0) THEN
            stressNew(k,1)=0.0D0
          ELSE IF (TRIAL.GE.EFAIL) THEN
            stressNew(k,1)=0.0D0
            IF (nstatev.GE.1) stateNew(k,1)=0.0D0
          ELSE
            stressNew(k,1)=TRIAL
          END IF
          DO i=2,ndir+nshr
            IF (stressNew(k,i).LT.0.0D0) stressNew(k,i)=0.0D0
          END DO
        END IF
      END DO
      RETURN
      END
