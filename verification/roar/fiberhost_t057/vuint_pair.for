C======================================================================
C     VUINTERACTION_BASELINE + PAIR LOGGER (T-057 Hub coupon cx057)
C     Contact law identical to T-056 baseline (the one that blew up).
C     Logs EVERY proximity point of EVERY call to vuint_pair.txt.
C     Small coupon only. Run with ONE thread (SAVE counters).
C     CALL rows : call kinc jflag1 nblock nnodstate nnodmst nstates
C                 rdata1..4
C     PT rows   : call kinc k slv mst1..4 pen st1in st2in s1in d0
C                 press area force xs ys zs n1 n2 n3
C======================================================================
      SUBROUTINE VUINTERACTION (
     *     STRESS, FLUXSLV, FLUXMST,
     *     STATE, SED,
     *     SFD, SCD, SPD, SVD,
     *     NBLOCK, NBLOCKANAL, NBLOCKEDGE,
     *     NNODSTATE, NNODSLV, NNODMST, NDIR,
     *     NSTATES, NPROPS, NTEMP, NFIELDS,
     *     JFLAGS, RDATA,
     *     SURFINT, SURFSLV, SURFMST,
     *     JSLVUID, JMSTUID, PROPS,
     *     PENETRATION, DRDISP, DROT, DIRCOS, STIFFDEF, CONDUCTDEF,
     *     COORDSLV, COORDMST, AREAPROX, SHAPESLV, SHAPEMST,
     *     TEMPSLV, TEMPMST, DTEMPSLV, DTEMPMST,
     *     FIELDSLV, FIELDMST, DFIELDSLV, DFIELDMST )
C
      INCLUDE 'vaba_param.inc'
C
      CHARACTER*80 SURFINT, SURFSLV, SURFMST
      DIMENSION JFLAGS(*), RDATA(*)
      DIMENSION JSLVUID(NNODSLV, NBLOCK), JMSTUID(NNODMST, NBLOCK)
      DIMENSION PROPS(NPROPS)
      DIMENSION PENETRATION(NBLOCK), DRDISP(NDIR, NBLOCK)
      DIMENSION DROT(2, 2, NBLOCK), DIRCOS(NDIR, NDIR, NBLOCK)
      DIMENSION STIFFDEF(NBLOCK), CONDUCTDEF(NBLOCK)
      DIMENSION COORDSLV(NDIR, NNODSLV, NBLOCK), COORDMST(NDIR, NBLOCK)
      DIMENSION AREAPROX(NBLOCK)
      DIMENSION TEMPSLV(NBLOCK), TEMPMST(NBLOCK)
      DIMENSION DTEMPSLV(NBLOCK), DTEMPMST(NBLOCK)
      DIMENSION FIELDSLV(NFIELDS, NBLOCK), FIELDMST(NFIELDS, NBLOCK)
      DIMENSION DFIELDSLV(NFIELDS, NBLOCK), DFIELDMST(NFIELDS, NBLOCK)
      DIMENSION STRESS(NDIR, NBLOCK), FLUXSLV(NBLOCK), FLUXMST(NBLOCK)
      DIMENSION STATE(NSTATES, NNODSTATE, NBLOCK)
      DIMENSION SED(NBLOCK), SFD(NBLOCK), SCD(NBLOCK), SPD(NBLOCK),
     *          SVD(NBLOCK)
C
      INTEGER K, IDIR, J, IU, LENOUT, NCALL, NPRT
      REAL*8 D, D_POS, D0, D_EFF, PRESS, KPEN, FRIC, KS
      REAL*8 DS1, DS2, TAU1, TAU2, TAU_MAG, TAU_CRIT, SCALE
      REAL*8 S1IN, ST1IN, ST2IN
      LOGICAL LOPEN
      CHARACTER*256 OUTDIR
      SAVE NCALL, NPRT, LOPEN
      DATA NCALL /0/, NPRT /0/, LOPEN /.FALSE./
C
      IU = 121
      NCALL = NCALL + 1
      IF (.NOT. LOPEN) THEN
        CALL VGETOUTDIR(OUTDIR, LENOUT)
        OPEN(UNIT=IU, FILE=OUTDIR(1:LENOUT)//'/vuint_pair.txt',
     *       STATUS='UNKNOWN')
        LOPEN = .TRUE.
        WRITE(IU,'(A)') '# CALL call kinc jflag1 nblock nnodstate '//
     *   'nnodmst nstates rdata1..4'
        WRITE(IU,'(A)') '# PT call kinc k slv mst1..4 pen st1in '//
     *   'st2in s1in d0 press area force xs ys zs n1 n2 n3'
      END IF
      IF (NPRT .LT. 2000000) THEN
        NPRT = NPRT + 1
        WRITE(IU,'(A,I9,I8,5I6,4ES13.5)') 'CALL ', NCALL, JFLAGS(2),
     *    JFLAGS(1), NBLOCK, NNODSTATE, NNODMST, NSTATES,
     *    RDATA(1), RDATA(2), RDATA(3), RDATA(4)
      END IF
C
      DO K = 1, NBLOCK
        IF (NPROPS .GE. 1 .AND. PROPS(1) .GT. 0.0D0) THEN
          KPEN = PROPS(1)
        ELSE
          KPEN = 2.0D11
        END IF
        FRIC = 0.01D0
        IF (NPROPS .GE. 2) FRIC = PROPS(2)
C
        D = PENETRATION(K)
        D_POS = MAX(D, 0.0D0)
        S1IN = STRESS(1, K)
        ST1IN = STATE(1, 1, K)
        ST2IN = STATE(2, 1, K)
        IF (STATE(2, 1, K) .LT. 0.5D0) THEN
          D0 = D_POS
          STATE(1, 1, K) = D0
          STATE(2, 1, K) = 1.0D0
        ELSE
          D0 = MIN(STATE(1, 1, K), D_POS)
          STATE(1, 1, K) = D0
        END IF
        D_EFF = MAX(0.0D0, D - D0)
        PRESS = KPEN * D_EFF
        STRESS(1, K) = PRESS
C
        IF (FRIC .GT. 0.0D0 .AND. PRESS .GT. 0.0D0) THEN
          DS1 = DRDISP(2, K)
          DS2 = 0.0D0
          IF (NDIR .GE. 3) DS2 = DRDISP(3, K)
          KS = KPEN
          TAU1 = STRESS(2, K) - KS * DS1
          TAU2 = 0.0D0
          IF (NDIR .GE. 3) TAU2 = STRESS(3, K) - KS * DS2
          TAU_MAG = SQRT(TAU1*TAU1 + TAU2*TAU2)
          TAU_CRIT = FRIC * PRESS
          IF (TAU_MAG .GT. TAU_CRIT .AND. TAU_MAG .GT. 1.0D-14) THEN
            SCALE = TAU_CRIT / TAU_MAG
            STRESS(2, K) = TAU1 * SCALE
            IF (NDIR .GE. 3) STRESS(3, K) = TAU2 * SCALE
          ELSE
            STRESS(2, K) = TAU1
            IF (NDIR .GE. 3) STRESS(3, K) = TAU2
          END IF
        ELSE
          DO IDIR = 2, NDIR
            STRESS(IDIR, K) = 0.0D0
          END DO
        END IF
C
        IF (NPRT .LT. 2000000) THEN
          NPRT = NPRT + 1
          WRITE(IU,'(A,I9,I8,I5,I8,4I8,15ES13.5)') 'PT ', NCALL,
     *      JFLAGS(2), K, JSLVUID(1,K),
     *      (JMSTUID(J,K), J=1,MIN(NNODMST,4)),
     *      (0, J=MIN(NNODMST,4)+1,4),
     *      D, ST1IN, ST2IN, S1IN, D0, PRESS, AREAPROX(K),
     *      PRESS*AREAPROX(K), COORDSLV(1,1,K), COORDSLV(2,1,K),
     *      COORDSLV(3,1,K), DIRCOS(1,1,K), DIRCOS(2,1,K),
     *      DIRCOS(3,1,K)
        END IF
C
        SED(K) = 0.5D0 * PRESS * D_EFF
        SFD(K) = 0.0D0
        SCD(K) = 0.0D0
        SPD(K) = 0.0D0
        SVD(K) = 0.0D0
        FLUXSLV(K) = 0.0D0
        FLUXMST(K) = 0.0D0
      END DO
      CALL FLUSH(IU)
C
      RETURN
      END
