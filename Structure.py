#-*- coding:utf-8 -*-

import os, sys, subprocess, random, time, re

if 'getstatusoutput' in dir(subprocess):
    from subprocess import getstatusoutput
else:
    from commands import getstatusoutput

############################################
#######    Internal function
############################################

def __build_SHAPE_constraint(shape_list, outFn):
    """
    shape_list              -- A list of SHAPE scores
    outFn                   -- File name to save
    
    Build a SHAPE constraint file for RNAstructure
    """
    SHAPE = open(outFn, 'w')
    
    for idx in range(len(shape_list)):
        if shape_list[idx] != "NULL":
            SHAPE.writelines("%d\t%s\n" % (idx+1, shape_list[idx]))
        else:
            SHAPE.writelines("%d\t%s\n" % (idx+1, -999))
    
    SHAPE.close()

def __build_single_seq_fasta(sequence, outFn):
    """
    sequence                -- Raw sequence
    outFn                   -- File name to save
    
    Build single-seq .fasta file for RNAstructure
    """
    SEQ = open(outFn, 'w')
    SEQ.writelines(">test\n%s\n" % (sequence, ))
    SEQ.close()

def __build_single_seq_file(sequence, outFn):
    """
    sequence                -- Raw sequence
    outFn                   -- File name to save
    
    Build single-seq .seq file for RNAstructure
    """
    SEQ = open(outFn, 'w')
    SEQ.writelines(";\nMySeq\n%s\n1\n" % (sequence, ))
    SEQ.close()

def __build_bp_constraint(bp_constraint, outFn):
    """ 
    bp_constraint           -- [[1,10], [2,9], [3,8]...] 1-based
    outFn                   -- File name to save
    
    Build a constraint file for RNAstructure
    """
    OUT = open(outFn, 'w')
    OUT.writelines("DS:\n-1\nSS:\n-1\nMod:\n-1\n")
    OUT.writelines("Pairs:\n")
    for left, right in bp_constraint:
        OUT.writelines("%s %s\n" % (left, right))
    
    OUT.writelines("-1 -1\n")
    OUT.writelines("FMN:\n-1\nForbids:\n-1 -1\n\n")
    OUT.close()

def __build_single_dot_file(sequence, dot, outFn, title='test_seq'):
    """
    sequence                -- Raw sequence
    dot                     -- Dot structure
    outFn                   -- File name to save
    title                   -- Sequence title
    
    Build a single sequence ct file for RNAstructure
    """
    assert len(sequence) == len(dot)
    open(outFn, 'w').writelines(">%s\n%s\n%s\n\n" % (title, sequence, dot))

############################################
#######    Structure prediction
############################################

def predict_structure(sequence, shape_list=[], bp_constraint=[], mfe=True, clean=True, si=-0.6, sm=1.8, md=None, verbose=False):
    """
    sequence                -- Raw sequence
    shape_list              -- A list of SHAPE scores
    bp_constraint           -- [[1,10], [2,9], [3,8]...] 1-based
    mfe                     -- Use MFE algorithm, which is faster
    clean                   -- Delete all tmp files
    si                      -- Intercept
    sm                      -- Slope
    md                      -- Maximum pairing distance between nucleotides.
    verbose                 -- Print command
    
    Predict RNA secondary structure using Fold or Fold-smp
    
    Require: Fold or Fold-smp, ct2dot
    """
    import General
    import shutil
    
    Fold = General.require_exec("Fold-smp", exception=False)
    if not Fold:
        Fold = General.require_exec("Fold")
    
    ct2dot = General.require_exec("ct2dot")
    
    randID = random.randint(1000000,9000000)
    
    ROOT = "/tmp/predict_structure_%s/" % (randID, )
    os.mkdir(ROOT)
    fa_file = ROOT + "input.fa"
    shape_file = ROOT + "input.shape"
    constrain_file = ROOT + "input.const"
    ct_file = ROOT + "output.ct"
    
    Fold_CMD = Fold + " %s %s -si %s -sm %s" % (fa_file, ct_file, si, sm)
    
    __build_single_seq_fasta(sequence, fa_file)
    
    if shape_list:
        assert len(sequence) == len(shape_list)
        __build_SHAPE_constraint(shape_list, shape_file)
        Fold_CMD += " --SHAPE " + shape_file
    
    if bp_constraint:
        __build_bp_constraint(bp_constraint, constrain_file)
        Fold_CMD += " --constraint " + constrain_file
    
    if mfe:
        Fold_CMD += " -mfe"
    
    if md:
        Fold_CMD += " --maxdistance " + str(md)
    
    Fold_CMD += ' > /dev/null'
    
    if verbose: 
        print(Fold_CMD)
    
    os.system(Fold_CMD)
    
    ct2dot_cmd = ct2dot + " %s %d /dev/stdout"
    
    if not mfe:
        return_code, return_string = getstatusoutput( "grep \"ENERGY\" %s | wc -l" % (ct_file, ) )
        structure_number = int( return_string.strip() )
        structure_list = []
        regex_cap_free_energy = re.compile("=\s*(\-+[\d\.]+)")
        for idx in range(structure_number):
            return_code, return_string = getstatusoutput( ct2dot_cmd % (ct_file, idx+1) )
            energy = float(regex_cap_free_energy.findall(return_string.split('\n')[0])[0])
            structure = return_string.split('\n')[2]
            structure_list.append( (energy, structure) )
    else:
        return_code, return_string = getstatusoutput( ct2dot_cmd % (ct_file, 1) )
        structure = return_string.split('\n')[2]
        structure_list = structure
    
    # clean
    if clean:
        shutil.rmtree(ROOT)
    
    return structure_list

def bi_fold(seq_1, seq_2, local_pairing=False, mfe=True, clean=True, is_dna=False, verbose=False):
    """
    seq_1                   -- Raw sequence 1
    seq_2                   -- Raw sequence 2
    local_pairing           -- Allow local base-pairing
    mfe                     -- Return the first interaction
    
    Predict RNA interaction using bifold or bifold-smp
    Return dotBracket if mfe is True
    Return [(energy1, dotBracket1), (energy2, dotBracket2)...]
    
    Require: bifold or bifold-smp, ct2dot
    """
    import General
    import shutil
    
    bifold = General.require_exec("bifold-smp", exception=False)
    if not bifold:
        bifold = General.require_exec("bifold")
    
    ct2dot = General.require_exec("ct2dot")
    
    randID = random.randint(1000000,9000000)
    ROOT = "/tmp/bi_fold_%s/" % (randID, )
    os.mkdir(ROOT)
    seq_1_fn = ROOT + "input_1.fa"
    seq_2_fn = ROOT + "input_2.fa"
    ct_fn = ROOT + "output.ct"
    
    __build_single_seq_fasta(seq_1, seq_1_fn)
    __build_single_seq_fasta(seq_2, seq_2_fn)
    
    CMD = bifold + " %s %s %s" % (seq_1_fn, seq_2_fn, ct_fn)
    
    if not local_pairing:
        CMD += " --intramolecular"
    
    if is_dna:
        CMD += " --DNA"
    
    CMD += " > /dev/null"
    
    if verbose:
        print(CMD)
    
    os.system(CMD)
    
    return_code, return_string = getstatusoutput( "grep ENERGY %s | wc -l" % (ct_fn, ) )
    structure_number = int( return_string.strip() )
    structure_list = []
    ct2dot_cmd = ct2dot + " %s %d /dev/stdout"
    
    for idx in range(structure_number):
        if mfe and idx == 1:
            break
        return_code, return_string = getstatusoutput( ct2dot_cmd % (ct_fn, idx+1) )
        lines = return_string.split('\n')
        energy = float(lines[0].strip().split()[-2])
        structure = return_string.split()[8]
        structure_list.append( (energy, lines[2]) )
    
    cur_seq = seq_1 + "III" + seq_2
    
    if clean:
        shutil.rmtree(ROOT)
    
    if mfe:
        return structure_list[0][1]
    else:
        return structure_list

def search_TT_cross_linking(sequence, dot):
    """
    sequence                -- Raw sequence
    dot                     -- Dotbracket structure
    
    Search TT cross-linking sites
    """
    cross_link_points = []
    
    sequence = sequence.replace("U", "T")
    
    ct_list = dot2ct(dot)
    for ct in ct_list:
        assert ct[0]<ct[1]<=len(sequence)
        
        top_left_base = top_center_base = top_right_base = '.'
        bot_left_base = bot_center_base = bot_right_base = '.'
        
        if ct[1] != len(sequence):
            top_left_base = sequence[ct[1]]
        top_center_base = sequence[ct[1]-1]
        top_right_base = sequence[ct[1]-2]
        
        if ct[0] != 1:
            bot_left_base = sequence[ct[0]-2]
        bot_center_base = sequence[ct[0]-1]
        bot_right_base = sequence[ct[0]]
        
        top_U = True if top_center_base == 'T' else False
        bot_U = True if bot_center_base == 'T' else False
        
        top_left_flanking_U = True if top_left_base == 'T' else False
        top_right_flanking_U = True if top_right_base == 'T' else False
        
        bot_left_flanking_U = True if bot_left_base == 'T' else False
        bot_right_flanking_U = True if bot_right_base == 'T' else False
        
        if top_U and bot_left_flanking_U:
            cross_link_points.append( (ct[0]-1, ct[1]) )
        
        if top_U and bot_right_flanking_U:
            cross_link_points.append( (ct[0]+1, ct[1]) )
        
        if bot_U and top_left_flanking_U:
            cross_link_points.append( (ct[0], ct[1]+1) )
        
        if bot_U and top_right_flanking_U:
            cross_link_points.append( (ct[0], ct[1]-1) )
    
    cross_link_points.sort(key=lambda x: x[0])
    uniq_cross_link_points = []
    for points in cross_link_points:
        if points not in uniq_cross_link_points:
            uniq_cross_link_points.append(points)
    
    return uniq_cross_link_points

def get_a_dyalign_conf_model():
    DYALIGN_CONF = """
    inseq1 = %s
    inseq2 = %s
    outct = %s
    outct2 = %s
    aout = %s
    
    num_processors = %s
    
    # shape_1_file = 
    # shape_2_file = 
    
    shapeslope1 = 1.8
    shapeintercept1 = -0.6
    shapeslope2 = 1.8
    shapeintercept2 = -0.6
    
    fgap = .4
    maxtrace = 750
    percent = 20
    bpwin = 2
    awin = 1
    insert = 1
    singlefold_subopt_percent = 30
    imaxseparation = -99
    optimal_only = 0
    local = 0
    dsv_templated = 0
    ct_templated = 0
    DNA = 0
    temperature = 310.15  
    
    # savefile = dot.save
    """
    lines = DYALIGN_CONF.strip().split('\n')
    for i in range(len(lines)):
        lines[i] = lines[i].lstrip()
    
    DYALIGN_CONF = "\n".join(lines)
    return DYALIGN_CONF

def dyalign(seq_1, seq_2, shape_list_1=[], shape_list_2=[], clean=True, thread_nums=1, verbose=False):
    """
    seq_1                   -- Raw sequence 1
    seq_2                   -- Raw sequence 2
    shape_list_1            -- A list of shape for sequence 1
    shape_list_2            -- A list of shape for sequence 2
    clean                   -- Delete all tmp files
    thread_nums             -- Treads number
    verbose                 -- Print command
    
    Find common secondary structure given two sequences
    
    Require: dynalign_ii or dynalign_ii-smp
    
    return dot_1, dot_2, aligned_seq_1, aligned_seq_2, aligned_dot_1, aligned_dot_2
    """
    
    if shape_list_1: 
        assert len(seq_1) == len(shape_list_1)
    if shape_list_2: 
        assert len(seq_2) == len(shape_list_2)
    
    import General
    import random, os, sys
    import shutil

    dynalign = General.require_exec("dynalign_ii-smp", exception=False)
    if not dynalign:
        dynalign = General.require_exec("dynalign_ii")
    
    randID = random.randint(1000000,9000000)
    ROOT = "/tmp/dyalign_%s/" % (randID, )
    os.mkdir(ROOT)
    fa_file = ROOT + "input.fa"
    afa_file = ROOT + "output.afa"
    
    conf_file = ROOT + "configure.conf"
    seq1_file = ROOT + "seq_1.seq"
    seq2_file = ROOT + "seq_2.seq"
    shape1_file = ROOT + "shape_1.shape"
    shape2_file = ROOT + "shape_2.shape"
    ct1_file = ROOT + "ct_1.ct"
    ct2_file = ROOT + "ct_2.ct"
    align_file = ROOT + "align.txt"
    
    CONF = get_a_dyalign_conf_model() % (seq1_file, seq2_file, ct1_file, ct2_file, align_file, thread_nums)
    
    __build_single_seq_file(seq_1, seq1_file)
    __build_single_seq_file(seq_2, seq2_file)
    if shape_list_1:
        __build_SHAPE_constraint(shape_list_1, hape1_file)
        CONF += "\nshape_1_file = "+hape1_file
    if shape_list_2:
        __build_SHAPE_constraint(shape_list_2, shape2_file)
        CONF += "\nshape_2_file = "+shape2_file
    
    open(conf_file, 'w').writelines(CONF+"\n")
    
    CMD = dynalign + " " + conf_file + " > /dev/null"
    if verbose:
        print(CMD)
    os.system(CMD)
    
    dot_1 = dot_from_ctFile(ct1_file, number=1)[1]
    dot_2 = dot_from_ctFile(ct2_file, number=1)[1]
    align_seq_1, align_seq_2 = read_DYA_alignment(align_file)
    align_dot_1 = dot_to_alignDot(dot_1, align_seq_1)
    align_dot_2 = dot_to_alignDot(dot_2, align_seq_2)
    
    if clean:
        shutil.rmtree(ROOT)
    
    return (dot_1, dot_2, align_seq_1, align_seq_2, align_dot_1, align_dot_2)

def get_a_multialign_conf_model():
    MULTIALIGN_CONF = """
    InSeq = {%s}
    OutCT = {%s}
    
    Alignment = %s
    SequenceNumber = %s
    
    DNA = 0
    SHAPEintercept = %s
    SHAPEslope = %s
    Temperature = 310.15
    Processors = %s
    
    Iterations = 2
    KeepIntermediate = 0
    MaxDsvChange = 1
    maxdsvchange = 1
    Random = 0
    
    Gap = 0.4
    Insert = 1
    Local = 0
    MaxPercent = 20
    MaxPercentSingle = 30
    MaxStructures = 750
    Separation = -99
    WindowAlign = 1
    WindowBP = 2
    """
    lines = MULTIALIGN_CONF.strip().split('\n')
    for i in range(len(lines)):
        lines[i] = lines[i].lstrip()
    
    MULTIALIGN_CONF = "\n".join(lines)
    return MULTIALIGN_CONF

def multialign(seq_list, shape_list_list=[], si=-0.6, sm=1.8, thread_nums=1, clean=True, verbose=False):
    """
    seq_list                -- A list of sequences
    shape_list              -- A list of SHAPE scores list
    si                      -- Intercept
    sm                      -- Slope
    clean                   -- Delete all tmp files
    thread_nums             -- Treads number
    verbose                 -- Print command
    
    Find common secondary structure given multiple sequences
    
    Require: multilign or multilign-smp
    
    Return dot_list, aligned_seq_list, aligned_dot_list
    """
    
    for i in range(len(shape_list_list)):
        assert len(shape_list_list[i]) == len(seq_list[i])

    import General
    import random, os, sys
    import shutil
    
    multilign = General.require_exec("multilign-smp", exception=False)
    if not multilign:
        multilign = General.require_exec("multilign")
    
    randID = random.randint(1000000,9000000)
    ROOT = "/tmp/multialign_%s/" % (randID, )
    os.mkdir(ROOT)
    fa_file = ROOT + "input.fa"
    afa_file = ROOT + "output.afa"
    
    conf_file = ROOT + "configure.conf"
    align_file = ROOT + "align.txt"
    
    seq_files = ""
    ct_files = ""
    for i in range(len(seq_list)):
        seq_files += ROOT+"seq_%s.seq;" % (i, )
        ct_files += ROOT+"structure_%s.ct;" % (i, )
    
    CONF = get_a_multialign_conf_model() % (seq_files, ct_files, align_file, len(seq_list), si, sm, thread_nums)
    
    shape_files = ""
    for i in range(len(shape_list_list)):
        shapeF = ROOT+"shape_%s.shape" % (i, )
        shape_files += shapeF + ";"
        CONF += "\nSHAPE%s = %s" % (i, shapeF)
    
    seq_file_list = seq_files.strip(";").split(";")
    ct_file_list = ct_files.strip(";").split(";")
    shape_file_list = shape_files.strip(';').split(';')
    
    for i,seq_file in enumerate(seq_file_list):
        __build_single_seq_file(seq_list[i].upper(), seq_file)
    
    for i,shape_file in enumerate(shape_file_list):
        if shape_file:
            __build_SHAPE_constraint(shape_list_list[i], shape_file)
    
    open(conf_file, 'w').writelines(CONF+"\n")
    
    CMD = multilign + " "+conf_file + " > /dev/null"
    if verbose:
        print(CMD)
    os.system(CMD)
    
    dot_list = []
    for i,ct_file in enumerate(ct_file_list):
        dot = dot_from_ctFile(ct_file, number=1)[1]
        dot_list.append(dot)
    
    aligned_seq_list = read_MULTI_alignment(align_file)
    align_dot_list = []
    for seq, dot, align_seq in zip(seq_list, dot_list, aligned_seq_list):
        aligned_dot = dot_to_alignDot(dot, align_seq)
        align_dot_list.append(aligned_dot)
    
    if clean:
        shutil.rmtree(ROOT) 
    
    return dot_list, aligned_seq_list, align_dot_list

def estimate_energy(sequence, dot, shape_list=[], simple=True, si=-0.6, sm=1.8, is_dna=False, clean=True, verbose=False):
    """
    sequence                -- Raw sequence
    dot                     -- Dot-bracket structure
    shape_list              -- A list of SHAPE scores
    simple                  -- Use simple energy function that is the same used in Fold/Fold-smp
    si                      -- Intercept
    sm                      -- Slope
    clean                   -- Delete all tmp files
    verbose                 -- Print command
    
    Calculate the folding free energy change of a structure
    
    Require: efn2 or efn2-smp
    """
    import General
    import shutil
    
    assert len(sequence) == len(dot)
    
    efn2 = General.require_exec("efn2-smp", exception=False)
    if not efn2:
        efn2 = General.require_exec("efn2")
    
    randID = random.randint(1000000,9000000)
    
    ROOT = "/tmp/estimate_energy_%s/" % (randID, )
    os.mkdir(ROOT)
    shape_file = ROOT + "input.shape"
    energy_file = ROOT + "energy.txt"
    ct_file = ROOT + "input.ct"
    
    efn2_CMD = efn2 + " %s %s -si %s -sm %s" % (ct_file, energy_file, si, sm)
    
    write_ctFn({"test": sequence}, {"test": dot}, ct_file)
    
    if shape_list:
        assert len(sequence) == len(shape_list)
        __build_SHAPE_constraint(shape_list, shape_file)
        efn2_CMD += " --SHAPE " + shape_file
    
    if simple:
        efn2_CMD += " --simple"
    
    if is_dna:
        efn2_CMD += " --DNA"
    
    efn2_CMD += ' > /dev/null'
    
    if verbose: 
        print(efn2_CMD)
    
    os.system(efn2_CMD)
    
    energy = float(open(energy_file).readline().strip().split()[-1])
    
    # clean
    if clean:
        shutil.rmtree(ROOT)
    
    return energy

def partition(sequence, shape_list=[], bp_constraint=[], clean=True, si=-0.6, sm=1.8, md=None, verbose=False):
    """
    sequence                -- Raw sequence
    shape_list              -- A list of SHAPE scores
    bp_constraint           -- [[1,10], [2,9], [3,8]...] 1-based
    clean                   -- Delete all tmp files
    si                      -- Intercept
    sm                      -- Slope
    md                      -- Maximum pairing distance between nucleotides.
    verbose                 -- Print command
    
    Estimate partition function using partition or partition-smp
    
    Require: partition or partition-smp, ProbabilityPlot
    """
    import General
    import shutil
    
    partition = General.require_exec("partition-smp", exception=False)
    if not partition:
        partition = General.require_exec("partition")
    
    ProbabilityPlot = General.require_exec("ProbabilityPlot")
    
    randID = random.randint(1000000,9000000)
    
    ROOT = "/tmp/partition_%s/" % (randID, )
    os.mkdir(ROOT)
    fa_file = ROOT + "input.fa"
    shape_file = ROOT + "input.shape"
    constrain_file = ROOT + "input.const"
    pfs_file = ROOT + "output.pfs"
    pairingProb_file = ROOT + "pairingprob.txt"
    
    partition_CMD = partition + " %s %s -si %s -sm %s" % (fa_file, pfs_file, si, sm)
    
    __build_single_seq_fasta(sequence, fa_file)
    
    if shape_list:
        assert len(sequence) == len(shape_list)
        __build_SHAPE_constraint(shape_list, shape_file)
        partition_CMD += " --SHAPE " + shape_file
    
    if bp_constraint:
        __build_bp_constraint(bp_constraint, constrain_file)
        partition_CMD += " --constraint " + constrain_file
    
    if md:
        partition_CMD += " --maxdistance " + str(md)
    
    partition_CMD += ' -q > /dev/null'
    
    if verbose: 
        print(partition_CMD)
    
    os.system(partition_CMD)
    
    ProbabilityPlot_cmd = ProbabilityPlot + " %s %s -t > /dev/null" % (pfs_file, pairingProb_file)
    os.system(ProbabilityPlot_cmd)
    
    pairingProb = []
    for lc,line in enumerate(open(pairingProb_file)):
        if lc>1:
            nc1,nc2,log10Prob = line.strip().split()
            pairingProb.append( (int(nc1),int(nc2),10**(-float(log10Prob))) )
    
    # clean
    if clean:
        shutil.rmtree(ROOT)
    
    return pairingProb

############################################
#######    Format conversion
############################################

def dot2ct(dot):
    """
    dot                     -- Dotbracket structure
    
    Convert dotbracket structure to list
    ..((..))..  =>  [(3, 8), (4, 7)]
    """
    
    stack = []
    ctList = []
    
    for idx,symbol in enumerate(dot):
        if symbol in ('(', '[', '{', '<'):
            stack.append( (idx+1, symbol) )
        elif symbol in '.-_=:,':
            pass
        else:
            for i in range( len(stack)-1, -1, -1 ):
                if stack[i][1]+symbol in ("()", "[]", r"{}", "<>"):
                    ctList.append( (stack[i][0], idx+1) )
                    del stack[i]
                    break
                else:
                    pass
    
    if len(stack) != 0:
        sys.stderr.writelines("Error: Bad dotbracket structure\n")
        raise NameError("Error: Bad dotbracket structure")
    
    ctList.sort()
    return ctList

def dot2bpmap(dot):
    """
    dot                 -- Dotbracket structure
    
    Convert dotbracket structure to dictionary
    ..(((....)))..   =>    {3: 12, 4: 11, 5: 10, 10: 5, 11: 4, 12: 3}
    """
    stack = []
    bpmap = {}
    
    for idx,symbol in enumerate(dot):
        if symbol in ('(', '[', '{', '<'):
            stack.append( (idx+1, symbol) )
        elif symbol == '.-_=:,':
            pass
        else:
            for i in range( len(stack)-1, -1, -1 ):
                if stack[i][1]+symbol in ("()", "[]", r"{}", "<>"):
                    bpmap[idx+1] = stack[i][0]
                    bpmap[stack[i][0]] = idx+1
                    del stack[i]
                    break
                else:
                    pass
    
    if len(stack) != 0:
        sys.stderr.writelines("Error: Bad dotbracket structure\n")
        raise NameError("Error: Bad dotbracket structure")
    
    return bpmap

def parse_pseudoknot(ctList):
    """
    ctList              -- paired-bases: [(3, 8), (4, 7)]
    
    Parse pseusoknots from clList
    Return:
        [ [(3, 8), (4, 7)], [(3, 8), (4, 7)], ... ]
    """
    ctList.sort(key=lambda x:x[0])
    ctList = [ it for it in ctList if it[0]<it[1] ]
    paired_bases = set()
    for lb,rb in ctList:
        paired_bases.add(lb)
        paired_bases.add(rb)
    
    # Collect duplex
    duplex = []
    cur_duplex = [ ctList[0] ]
    for i in range(1, len(ctList)):
        bulge_paired = False
        for li in range(ctList[i-1][0]+1, ctList[i][0]):
            if li in paired_bases:
                bulge_paired = True
                break
        if ctList[i][1]+1>ctList[i-1][1]:
            bulge_paired = True
        else:
            for ri in range(ctList[i][1]+1, ctList[i-1][1]):
                if ri in paired_bases:
                    bulge_paired = True
                    break
        if bulge_paired:
            duplex.append(cur_duplex)
            cur_duplex = [ ctList[i] ]
        else:
            cur_duplex.append(ctList[i])
    if cur_duplex:
        duplex.append(cur_duplex)
    
    # Discriminate duplex are pseudoknot
    Len = len(duplex)
    incompatible_duplex = []
    for i in range(Len):
        for j in range(i+1, Len):
            bp1 = duplex[i][0]
            bp2 = duplex[j][0]
            if bp1[0]<bp2[0]<bp1[1]<bp2[1] or bp2[0]<bp1[0]<bp2[1]<bp1[1]:
                incompatible_duplex.append((i, j))
    
    pseudo_found = []
    while incompatible_duplex:
        # count pseudo
        count = {}
        for l,r in incompatible_duplex:
            count[l] = count.get(l,0)+1
            count[r] = count.get(r,0)+1
        
        # find most possible pseudo
        count = list(count.items())
        count.sort( key=lambda x: (x[1],-len(duplex[x[0]])) )
        possible_pseudo = count[-1][0]
        pseudo_found.append(possible_pseudo)
        i = 0
        while i<len(incompatible_duplex):
            l,r = incompatible_duplex[i]
            if possible_pseudo in (l,r):
                del incompatible_duplex[i]
            else:
                i += 1
    
    pseudo_duplex = []
    for i in pseudo_found:
        pseudo_duplex.append(duplex[i])
    
    return pseudo_duplex

def ct2dot(ctList, length):
    """
    ctList              -- paired-bases: [(3, 8), (4, 7)]
    length              -- Length of structure
    
    Convert ctlist structure to dot-bracket
    [(3, 8), (4, 7)]  => ..((..))..
    """
    dot = ['.']*length
    if len(ctList) == 0:
        return "".join(dot)
    ctList = sorted(ctList, key=lambda x:x[0])
    ctList = [ it for it in ctList if it[0]<it[1] ]
    pseudo_duplex = parse_pseudoknot(ctList)
    for l,r in ctList:
        dot[l-1] = '('
        dot[r-1] = ')'
    dottypes = [ '<>', r'{}', '[]' ]
    if len(pseudo_duplex)>len(dottypes):
        print("Warning: too many psudoknot type: %s>%s" % (len(pseudo_duplex),len(dottypes)))
    for i,duplex in enumerate(pseudo_duplex):
        for l,r in duplex:
            dot[l-1] = dottypes[i%3][0]
            dot[r-1] = dottypes[i%3][1]
    return "".join(dot)

def write_ctFn(Fasta, Dot, ctFn):
    """
    Fasta           -- A dictionary { tid1: seq1, tid2: seq2, ... }
    Dot             -- A dictionary { tid1: dotbracket1, tid2: dotbracket2, ... }
    ctFn            -- .ct file
    
    Save dot-bracket structure to .ct file
    """
    import General
    General.write_ct(Fasta, Dot, ctFn)

def dot2align(seq, dot):
    """
    Convert secondary structure to aligned sequence. 
    1. The sequence must contain III seperator;
    2. Base pairing is not allowed in single end
    
    seq         -- Sequence contain III seperator
    dot         -- Secondary structure
    
    Return left_aligned_seq, right_aligned_seq, aligned_symbols

    Example:
        seq = "TCCCTGGTGGTCTAGTGGTTAGGATTCGGCGCTCTIIIAGTGCGCCGAATCCTAACCACTAGACCACCAAGG"
        dot = "..((((((((((((((((((((((((((((((.((...)).))))))))))))))))))))))))))).)))"
        data = dot2align(seq, dot)
    """
    assert len(seq)==len(dot)
    III_index = seq.find("III")
    assert III_index != -1
    ls, le, rs, re = 0, III_index, III_index+3, len(seq)
    left_seq = seq[ls:le]
    right_seq = seq[rs:re][::-1]
    left_dot = dot[ls:le]
    right_dot = dot[rs:re][::-1]
    assert ')' not in left_dot
    assert '(' not in right_dot
    assert left_dot.count(')')==right_dot.count('(')
    
    left_aligned_seq = ""
    right_aligned_seq = ""
    aligned_symbols = ""
    i,j = 0,0
    while i<len(left_seq) and j<len(right_seq):
        if left_dot[i]=='(' and right_dot[j]==')':
            left_aligned_seq += left_seq[i]
            right_aligned_seq += right_seq[j]
            aligned_symbols += "|"
            i,j = i+1,j+1
        elif left_dot[i]=='(' and right_dot[j]=='.':
            left_aligned_seq += "-"
            right_aligned_seq += right_seq[j]
            aligned_symbols += " "
            j = j+1
        elif left_dot[i]=='.' and right_dot[j]==')':
            left_aligned_seq += left_seq[i]
            right_aligned_seq += "-"
            aligned_symbols += " "
            i = i+1
        elif left_dot[i]=='.' and right_dot[j]=='.':
            left_aligned_seq += left_seq[i]
            right_aligned_seq += right_seq[j]
            aligned_symbols += " "
            i,j = i+1,j+1
        else:
            print(left_dot[i], right_dot[j])
            raise RuntimeError("Unexpected Error")
    
    while i<len(left_seq):
        left_aligned_seq += left_seq[i]
        right_aligned_seq += "-"
        i = i+1
    
    while j<len(right_seq):
        left_aligned_seq += "-"
        right_aligned_seq += right_seq[j]
        j = j+1
    
    return left_aligned_seq, right_aligned_seq, aligned_symbols

############################################
#######     Read file
############################################

def dot_from_ctFile(ctFn, number=1):
    """
    ctFn                -- .ct file
    number              -- The structure id
    
    Read dot dotbracket from .ct file

    Require: ct2dot
    """
    import General
    ct2dot = General.require_exec("ct2dot")
    
    CMD = ct2dot + " %s %s /dev/stdout" % (ctFn, number)
    return_code, information = getstatusoutput(CMD)
    return information.strip().split('\n')[1:3]

def read_DYA_alignment(inFn):
    """
    inFn                -- File name of dyalign produced
    
    Read dyalign produced file
    """
    seq1, seq2 = [ it.strip() for it in open(inFn).readlines()[1:3] ][:2]
    assert( len(seq1) == len(seq2) )
    return seq1, seq2

def read_MULTI_alignment(inFile):
    alignseq = []
    for line in open(inFile):
        data = line.strip().split()
        alignseq.append(data[1])
    return alignseq

############################################
#######    Stem loop structure parse
############################################

def find_stem(dot, max_stem_gap=3, min_stem_len=5):
    """
    dot                 -- Dotbracket structure
    max_stem_gap        -- Maximun interior loop size
    min_stem_len        -- Minimun stem length
    
    Find stem loop structure
    """
    ctList = dot2ct(dot)
    
    vs = []
    ls = 0; le = 0; rs = 0; re = 0
    
    for pair in ctList:
        if ls == 0:
            ls = le = pair[0]
            rs = re = pair[1]
        elif abs(pair[0]-le)-1>max_stem_gap or abs(rs-pair[1])-1>max_stem_gap:
            if le-ls+1>=min_stem_len and re-rs+1>=min_stem_len:
                vs.append( (ls, le, rs, re) )
            ls = le = pair[0]
            rs = re = pair[1]
        else:
            le = pair[0]
            rs = pair[1]
    if le-ls+1 >= min_stem_len and re-rs+1>=min_stem_len:
        vs.append( (ls, le, rs, re) )
    return vs

def trim_stem(dot, stem, min_fix_stem_len=2):
    """
    dot                 -- Dotbracket structure
    stem                -- [left_start, left_end, right_start, right_end]
    min_fix_stem_len    -- Minimun stem length in the stem loop boundary
    
    Trim short stem from stem loop boundary
    """
    subDot = dot[ stem[0]-1:stem[3] ]
    fix_stems = find_stem(subDot, max_stem_gap=0, min_stem_len=1)
    #print fix_stems
    
    fix_stems.sort(key=lambda x: x[0])
    for i in range(len(fix_stems)):
        cstem = fix_stems[i]
        if cstem[1]-cstem[0]+1>=min_fix_stem_len:
            return (cstem[0]+stem[0]-1, stem[1], stem[2], cstem[3]+stem[0]-1)
    
    return None

def find_stem_loop(dot, max_loop_len=4, max_stem_gap=3, min_stem_len=5):
    """
    dot                 -- Dotbracket structure
    max_loop_len        -- Maximun loop size
    max_stem_gap        -- Maximun interior loop size
    min_stem_len        -- Minimun stem length
    
    Find stem loops structure
    """
    stems = find_stem(dot, max_stem_gap=max_stem_gap, min_stem_len=min_stem_len)
    
    stem_loops = []
    for stem in stems:
        loopLen = stem[2]-stem[1]-1
        if loopLen <= max_loop_len:
            stem_loops.append( stem )
    
    return stem_loops

def find_bulge_interiorLoop(dot, stem):
    """
    dot                 -- Dotbracket structure
    stem                -- [left_start, left_end, right_start, right_end]
    
    Fint bulge and interiorLoop from stem loop

    Return bulge_list, interiorLoop_list
    
    Example:
        seq= "UCUAGGUGAUUUCUGUGAAAUCGAGCCCACUUGAUUGUUUCUGUGAAACACUCUA"
        dot = "....(((((((((...))))))..))).....((.((((((...)))))).)).."
        find_stem(dot, max_stem_gap=1, min_stem_len=5)
        stemLoop = find_stem_loop(dot, max_loop_len=3, max_stem_gap=3, min_stem_len=5)
        bulge, interiorLoop = find_bulge_interiorLoop(dot, stemLoop[0])
    """
    bulge = []
    interiorLoop = []
    
    ls,le,rs,re = stem
    i = le
    j = rs
    while i >= ls and j <= re:
        while i>=ls and j<=re and dot[i-1]!='.' and dot[j-1]!='.':
            i -= 1
            j += 1
        if i < ls or j > re:
            break
        
        if dot[i-1]!='.' and dot[j-1]=='.':
            start = j
            j += 1
            while j<=re and dot[j-1]=='.':
                j += 1
            interiorLoop.append( (start, j-1) )
        
        if dot[i-1]=='.' and dot[j-1]!='.':
            start = i
            i -= 1
            while i>=ls and dot[i-1]=='.':
                i -= 1
            interiorLoop.append( (i+1, start) )
        
        if dot[i-1]=='.' and dot[j-1]=='.':
            l_s = i
            r_s = j
            i -= 1
            j += 1
            while j<=re and dot[j-1]=='.':
                j += 1
            while i>=ls and dot[i-1]=='.':
                i -= 1
            bulge.append( (i+1,l_s,r_s,j-1) )
    
    return bulge, interiorLoop

def calcSHAPEStructureScore(dot, shape_list, stem, params={}, report=False):
    """
    dot                 -- Dotbracket structure
    shape_list          -- A list of SHAPE values
    stem                -- [left_start, left_end, right_start, right_end]
    params              -- A dict to specify parameters
    report              -- Print more detailed information
    
    Calculate a SHAPE-Structure agreenment score
    """
    import numpy
    
    ls,le,rs,re = stem
    
    assert len(dot) == len(shape_list)
    assert shape_list[ls-1:re].count('NULL') == 0
    
    Params = { 
    'stem_inter_cutoff': 0.7, # lower, stricter
    'inter_pinish': 2,
    'stem_flanking_cutoff': 0.8, # lower, stricter
    'flanking_punish': 2,
    'loop_cutoff': 0.7, # higher, stricter
    'loop_bonus': 2,
    'loop_max_cutoff': 0.4, # higher, stricter
    'bulge_cutoff': 0.6, # higher, stricter
    'bulge_bonus_factor': 2,
    'interloop_cutoff': 0.6, # higher, stricter
    'interloop_factor': 3
    }
    Params.update(params)
    
    fixed_stems = find_stem(dot[ls-1:re], max_stem_gap=0, min_stem_len=1)
    fixed_stems = [ [it[0]+ls-1, it[1]+ls-1, it[2]+ls-1, it[3]+ls-1] for it in fixed_stems ]
    
    bulges, interiorLoops = find_bulge_interiorLoop(dot, stem)
    
    ##########
    ##  Fix stems
    ##########
    
    stem_score = 0
    stem_base = 0
    stem_penalty = 0
    for fixStem in fixed_stems:
        sub_ls,sub_le,sub_rs,sub_re = fixStem
        assert sub_le-sub_ls == sub_re-sub_rs
        stem_len = sub_le-sub_ls+1
        assert stem_len >= 1
        
        if stem_len == 1:
            stem_score += (1-float(shape_list[ sub_ls-1 ])) + (1-float(shape_list[ sub_rs-1 ]))
            #stem_score /= 2
            stem_base += 2
            continue
        
        ave_med = 0
        if stem_len>2:
            left_inter = shape_list[ sub_ls:sub_le-1 ]
            right_inter = shape_list[ sub_rs:sub_re-1 ]
            inter = [ float(it) for it in left_inter+right_inter ]
            inter.sort()
            ave_med = (1-numpy.mean(inter[-2:]))*0.6 + (1-numpy.mean(inter))*0.4
            if numpy.mean(inter[-2:]) > Params['stem_inter_cutoff']:
                stem_penalty += Params['inter_pinish']
        
        flank = [ shape_list[sub_ls-1], shape_list[sub_le-1], shape_list[sub_rs-1], shape_list[sub_re-1] ]
        flank = [ float(it) for it in flank ]
        flank.sort()
        ave_flank = 1-numpy.mean(flank)
        if numpy.mean(flank[-2:]) > Params['stem_flanking_cutoff']:
            stem_penalty += Params['flanking_punish']
        
        stem_score += ave_med*(stem_len-2)*2 + ave_flank * 4
        stem_base += stem_len*2
    
    ##########
    ##  Loop
    ##########
    
    loop_score = 0
    loop_base = 0
    loop_bonus = 0
    loop_penalty = 0
    
    loop_shape = shape_list[le:rs-1]
    loop_shape = [ float(it) for it in loop_shape ]
    loop_shape.sort()
    ave_loop = numpy.mean(loop_shape[-2:])*0.6 + numpy.mean(loop_shape)*0.4
    loop_base = rs-le-1
    loop_score = ave_loop * loop_base
    if numpy.mean(loop_shape[-2:]) > Params['loop_cutoff']:
        loop_bonus = Params['loop_bonus']
    if loop_shape[-1] < Params['loop_max_cutoff']:
        loop_penalty = (1-loop_shape[-1]) * len(loop_shape)
    
    ##########
    ##  Bulge
    ##########
    
    bulge_score = 0
    bulge_base = 0
    bulge_bonus = 0
    
    for b_ls,b_le,b_rs,b_re in bulges:
        
        ave_flank_left = (float(shape_list[b_ls-2])+float(shape_list[b_le]))/2
        ave_flank_right = (float(shape_list[b_rs-2])+float(shape_list[b_re]))/2
        
        left_shape = shape_list[ b_ls-1:b_le ]
        right_shape = shape_list[ b_rs-1:b_re ]
        
        left_shape = [ float(it) for it in left_shape ]
        right_shape = [ float(it) for it in right_shape ]
        #print numpy.mean(left_shape), ave_flank_left
        if numpy.mean(left_shape) - ave_flank_left > Params['bulge_cutoff']:
            bulge_bonus += Params['bulge_bonus_factor'] * len(left_shape)
        else:
            bulge_score += sum(left_shape)
        if numpy.mean(right_shape) - ave_flank_right > Params['bulge_cutoff']:
            bulge_bonus += Params['bulge_bonus_factor'] * len(right_shape)
        else:
            bulge_score += sum(right_shape)
        
        bulge_base += len(left_shape) + len(right_shape)
    
    ##########
    ##  Interiror loop
    ##########
    
    intLoop_score = 0
    intLoop_base = 0
    intLoop_bonus = 0
    
    for i_ls,i_le in interiorLoops:
        
        ave_flank_left = (float(shape_list[i_ls-2])+float(shape_list[i_le]))/2
        medium = [ float(it) for it in shape_list[i_ls-1:i_le] ]
        if numpy.mean(medium) - ave_flank_left > Params['interloop_cutoff']:
            intLoop_bonus += Params['interloop_factor'] * len(medium)
        else:
            intLoop_score += sum(medium)
        
        intLoop_base += len(medium)
    
    stem_len = re-ls+1
    final_score = (stem_score-stem_penalty) + (loop_score+loop_bonus-loop_penalty) + (bulge_score+bulge_bonus) + (intLoop_score+intLoop_bonus)
    final_score /= stem_len
    
    assert stem_len == stem_base + loop_base + bulge_base + intLoop_base
    
    if report:
        print("stem_score: %.3f; stem_penalty: %3.f; stem_base: %s" % (stem_score, stem_penalty, stem_base))
        print("loop_score: %.3f; loop_bonus: %3.f; loop_penalty: %3.f; loop_base: %s" % (loop_score, loop_bonus, loop_penalty, loop_base))
        print("bulge_score: %.3f; bulge_bonus: %3.f; bulge_base: %s" % (bulge_score, bulge_bonus, bulge_base))
        print("intLoop_score: %.3f; intLoop_bonus: %3.f; intLoop_base: %s" % (intLoop_score, intLoop_bonus, intLoop_base))
    
    return round(final_score, 3)

def sliding_score_stemloop_noshape(sequence, max_loop_len=8, max_stem_gap=3, min_stem_len=5, start=0, end=None, wSize=200, wStep=100):
    """
    sequence            -- Raw sequence
    start               -- Start site
    end                 -- End site
    wSize               -- Window size
    wStep               -- Window step
    
    Find stem loops in sequence with a sliding window
    
    Return [ ((ls,le,rs,re), stemloop_dot), ... ]
    
    Require Fold or Fold-smp
    """
    import numpy
    
    Len = len(sequence)
    if not end:
        end = Len
    
    fine_stemloops = []
    start = start
    while start+wSize/2<end:
        curSeq = sequence[start:start+wSize]
        curSS = predict_structure(curSeq, verbose=False)
        
        stem_loops = find_stem_loop(curSS, max_loop_len=max_loop_len, max_stem_gap=max_stem_gap, min_stem_len=min_stem_len)
        trimed_stem_loops = []
        for sl in stem_loops:
            trimedSL = trim_stem(curSS, sl, min_fix_stem_len=3)
            if trimedSL:
                if trimedSL[1]-trimedSL[0]>=5:
                    trimed_stem_loops.append(trimedSL)
        global_stem_loops = [ [sl[0]+start, sl[1]+start, sl[2]+start, sl[3]+start] for sl in trimed_stem_loops ]
        
        for sl,gsl in zip(trimed_stem_loops, global_stem_loops):
            
            fine_stemloops.append( ( gsl, curSS[ sl[0]-1:sl[3] ] ) )
        
        start += wStep
    
    fine_stemloops.sort(key=lambda x: x[0][0], reverse=True)
    i = 1
    while i<len(fine_stemloops):
        l_ls,l_le,l_rs,l_re = fine_stemloops[i-1][0]
        n_ls,n_le,n_rs,n_re = fine_stemloops[i][0]
        if l_ls <= n_re and n_ls <= l_re:
            if l_re-l_ls > n_re-n_ls:
                del fine_stemloops[i]
            else:
                del fine_stemloops[i-1]
        else:
            i += 1
    
    fine_stemloops.sort(key=lambda x: x[0][0], reverse=False)
    return fine_stemloops

def sliding_score_stemloop_shape(sequence, shape_list, max_loop_len=8, max_stem_gap=3, min_stem_len=5, start=0, end=None, wSize=200, wStep=100, skip_noshape=True):
    """
    sequence            -- Raw sequence
    shape_list          -- A list of SHAPE values
    start               -- Start site
    end                 -- End site
    wSize               -- Window size
    wStep               -- Window step
    skip_noshape        -- Skip those regions without SHAPE values to save time
    
    Find stem loops in sequence with a sliding window
    
    Require Fold or Fold-smp
    """
    import numpy
    
    Len = len(sequence)
    assert Len == len(shape_list)
    if not end:
        end = Len
    
    stemloop_score = []
    start = start
    while start+wSize/2<end:
        curSeq = sequence[start:start+wSize]
        curShape = shape_list[start:start+wSize]
        if skip_noshape and 1.0*(len(curShape)-curShape.count('NULL'))/len(curShape) < 0.3:
            start += wStep
            continue
        
        curSS = predict_structure(curSeq, curShape, verbose=False)
        
        stem_loops = find_stem_loop(curSS, max_loop_len=max_loop_len, max_stem_gap=max_stem_gap, min_stem_len=min_stem_len)
        trimed_stem_loops = []
        for sl in stem_loops:
            trimedSL = trim_stem(curSS, sl, min_fix_stem_len=3)
            if trimedSL:
                if trimedSL[1]-trimedSL[0]>=5:
                    trimed_stem_loops.append(trimedSL)
        global_stem_loops = [ [sl[0]+start, sl[1]+start, sl[2]+start, sl[3]+start] for sl in trimed_stem_loops ]
        
        for sl,gsl in zip(trimed_stem_loops, global_stem_loops):
            
            stemshape = curShape[ sl[0]-1:sl[3] ]
            if stemshape.count('NULL') > 0: continue
            score = calcSHAPEStructureScore(curSS, curShape, sl, report=False)
            stemloop_score.append( ( gsl, curSS[ sl[0]-1:sl[3] ], score ) )
        
        start += wStep
    
    stemloop_score.sort(key=lambda x: x[0][0], reverse=True)
    i = 1
    while i<len(stemloop_score):
        l_ls,l_le,l_rs,l_re = stemloop_score[i-1][0]
        n_ls,n_le,n_rs,n_re = stemloop_score[i][0]
        if l_ls <= n_re and n_ls <= l_re:
            if stemloop_score[i-1][2] > stemloop_score[i][2]:
                del stemloop_score[i]
            else:
                del stemloop_score[i-1]
        else:
            i += 1
    
    stemloop_score.sort(key=lambda x: x[2], reverse=True)
    return stemloop_score

def sliding_score_stemloop(sequence, shape_list=None, max_loop_len=8, max_stem_gap=3, min_stem_len=5, start=0, end=None, wSize=200, wStep=100, skip_noshape=True):
    """
    sequence            -- Raw sequence
    shape_list          -- A list of SHAPE values
    start               -- Start site
    end                 -- End site
    wSize               -- Window size
    wStep               -- Window step
    skip_noshape        -- Skip those regions without SHAPE values to save time
                           Only useful when shape_list is provided 
    
    Find stem loops in sequence with a sliding window
    
    Require Fold or Fold-smp
    """
    if shape_list:
        return sliding_score_stemloop_shape(sequence, shape_list=shape_list, max_loop_len=max_loop_len, max_stem_gap=max_stem_gap, min_stem_len=min_stem_len, start=start, end=end, wSize=wSize, wStep=wStep, skip_noshape=skip_noshape)
    else:
        return sliding_score_stemloop_noshape(sequence, max_loop_len=max_loop_len, max_stem_gap=max_stem_gap, min_stem_len=min_stem_len, start=start, end=end, wSize=wSize, wStep=wStep)

############################################
#######    Multiple-local alignment and homology
############################################

def multi_alignment(seq_list, clean=True, verbose=False):
    """
    seq_list                -- A list of sequences
    clean                   -- Clean the tmp files
    verbose                 -- Print the command
    
    Global align multiple sequences
    
    Return [ aligned_seq1, aligned_seq2, aligned_seq3,... ]
    
    Require: muscle
    """
    import General
    import random, os, sys
    import shutil
    
    muscle = General.require_exec("muscle")
    
    randID = random.randint(1000000,9000000)
    ROOT = "/tmp/multi_alignment_%s/" % (randID, )
    os.mkdir(ROOT)
    fa_file = ROOT + "input.fa"
    afa_file = ROOT + "output.afa"
    
    OUT = open(fa_file, 'w')
    for i, sequence in enumerate(seq_list):
        OUT.writelines(">seq_%s\n%s\n" % (i+1, sequence))
    OUT.close()
    
    CMD = muscle+" -in %s -out %s" % (fa_file, afa_file)
    if verbose:
        print(CMD)
    else:
        CMD += " -quiet"
    os.system(CMD)
    
    aligned_list = []
    afa = General.load_fasta(afa_file)
    for i in range(1, len(seq_list)+1):
        aligned_list.append( afa["seq_"+str(i)] )
    
    if clean:
        shutil.rmtree(ROOT)
    
    return aligned_list

def kalign_alignment(seq_list, clean=True, verbose=False):
    """
    seq_list                -- A list of sequences
    clean                   -- Clean the tmp files
    verbose                 -- Print the command
    
    Local align multiple sequences
    
    Require kalign
    """
    import General
    import random, os, sys
    import shutil
    
    kalign = General.require_exec("kalign")
    
    randID = random.randint(1000000,9000000)
    ROOT = "/tmp/kalign_alignment_%s/" % (randID, )
    os.mkdir(ROOT)
    fa_file = ROOT + "input.fa"
    afa_file = ROOT + "output.afa"
        
    OUT = open(fa_file, 'w')
    for i, sequence in enumerate(seq_list):
        OUT.writelines(">seq_%s\n%s\n" % (i+1, sequence))
    OUT.close()
    
    CMD = kalign + " -in %s -out %s -format fasta" % (fa_file, afa_file)
    if verbose: 
        print(CMD)
    else:
        CMD += " -quiet"
    os.system(CMD)
    
    aligned_list = []
    afa = General.load_fasta(afa_file)
    for i in range(1, len(seq_list)+1):
        aligned_list.append( afa["seq_"+str(i)] )
    
    if clean:
        shutil.rmtree(ROOT)
    
    return aligned_list

def __split_cigar_forGS(cigar_code):
    """
    cigar_code          -- Cigar code
    
    Split cigar for global_search
    """
    import re, sys
    
    cigar_list = re.split("(M|I|D)", cigar_code)[:-1]
    
    if len(cigar_list) % 2 != 0:
        warning = "Error: %s is not a valid cigar code" % (cigar_code, )
        sys.stderr.writelines(warning+"\n")
        raise NameError(warning)
    
    cigar_pairs = []
    i = 0
    while i < len(cigar_list):
        cigar_pairs.append( (int(cigar_list[i]),  cigar_list[i+1]) )
        i += 2
    
    return cigar_pairs

def __format_ref_forGS(full_ref_seq, position, cigar_pairs):
    """
    full_ref_seq        -- Raw reference sequence
    position            -- Start position
    cigar_pairs         -- Split cigar pairs
    
    Convert raw sequence to aligned sequence for reference sequence
    """
    formated_ref = ""
    
    current_pos = position
    for Len,code in cigar_pairs:
        if code == 'M':
            formated_ref += full_ref_seq[ current_pos-1:current_pos+Len-1 ]
            current_pos += Len
        elif code == 'I':
            formated_ref += full_ref_seq[ current_pos-1:current_pos+Len-1 ]
            current_pos += Len
        elif code == 'D':
            formated_ref += "-"*Len
        else:
            sys.stderr.writelines("Error: Unexpected cigar code\n")
            raise NameError("Error: Unexpected cigar code")
    
    return formated_ref

def __format_query_forGS(full_query_seq, cigar_pairs):
    """
    full_query_seq      -- Raw query sequence
    cigar_pairs         -- Split cigar pairs
    
    Convert raw sequence to aligned sequence for query sequence
    """
    formated_query = ""
    
    current_pos = 1
    for Len,code in cigar_pairs:
        if code == 'M':
            formated_query += full_query_seq[ current_pos-1:current_pos+Len-1 ]
            current_pos += Len
        elif code == 'I':
            formated_query += "-"*Len
        elif code == 'D':
            formated_query += full_query_seq[ current_pos-1:current_pos+Len-1 ]
            current_pos += Len
        else:
            sys.stderr.writelines("Error: Unexpected cigar code\n")
            raise NameError("Error: Unexpected cigar code")
    
    return formated_query

def global_search(query_dict, ref_dict, thread_nums=1, min_identity=0.6, evalue=10, clean=True, verbose=False):
    """
    query_seq_dict              -- {seqID1:seq1, seqID2:seq2, seqID3:seq3,...}
    ref_seq_dict                -- {seqID1:seq1, seqID2:seq2, seqID3:seq3,...}
    min_identity                -- Minimum sequence identity
    evalue                      -- Evalue for search
    thread_nums                 -- Treads number
    clean                       -- Delete all tmp files
    verbose                     -- Print command
    
    Align short sequences to multiple long sequences.
    Return { query_id => [ (aligned_query_seq, ref_id, aligned_ref_seq, map_pos), ... ] }
    
    Require glsearch36
    """
    import General
    import random, os, sys
    import shutil
    
    glsearch36 = General.require_exec("glsearch36")
    
    randID = random.randint(1000000,9000000)
    ROOT = "/tmp/global_search_%s/" % (randID, )
    os.mkdir(ROOT)
    query_fa_file = ROOT + "query.fa"
    ref_fa_file = ROOT + "reference.afa"
    
    General.write_fasta(query_dict, query_fa_file)
    General.write_fasta(ref_dict, ref_fa_file)
    
    global_matches = {}
    
    ## -U mode permit U-C match
    CMD = glsearch36 + " -3 -m 8CC -n %s %s -T %s -E %s | grep -v \"^#\" | cut -f 1,2,3,9,13" % (query_fa_file, ref_fa_file, thread_nums, evalue)
    
    if verbose:
        print(CMD)
    
    for line in os.popen(CMD):
        query_id, ref_id, identity, map_pos, cigar = line.rstrip("\n").split()
        if float(identity) < min_identity*100: 
            continue
        
        cigar_pairs = __split_cigar_forGS(cigar)
        ref_seq = ref_dict[ref_id]
        query_seq = query_dict[query_id]
        
        map_pos = int(map_pos)
        
        formated_ref = __format_ref_forGS(ref_seq, map_pos, cigar_pairs)
        formated_query = __format_query_forGS(query_seq, cigar_pairs)
        
        try:
            global_matches[query_id].append( [formated_query, ref_id, formated_ref, map_pos] )
        except KeyError:
            global_matches[query_id] =  [ [formated_query, ref_id, formated_ref, map_pos] ]
    
    if clean:
        shutil.rmtree(ROOT)
    
    return global_matches

def align_find(aligned_seq, sub_seq):
    """
    aligned_seq             -- Aligned sequence with "-"
    sub_seq                 -- Sub sequence to search
    
    Find (start, end) in aligned sequence. Return (-1, -1) if not found
    """
    
    clean_seq = aligned_seq.replace("-", "")
    
    pos_start = clean_seq.find(sub_seq)
    pos_end = pos_start + len(sub_seq)
    if pos_start == -1:
        return (-1, -1)
    
    global_start = -1
    global_pos = 0
    alpha_pos = 0
    while alpha_pos != pos_end:
        if alpha_pos == pos_start:
            global_start = global_pos
        if aligned_seq[global_pos] != '-':
            alpha_pos += 1
        global_pos += 1
    
    return global_start+1, global_pos

def locate_homoseq(seq_dict, main_id, align_func, main_region=None, sub_seq=None):
    """
    seq_dict        -- Sequence dictionary
    main_id         -- Reference sequence id
    align_func      -- Multiple sequence alignment function: 
                        -> multi_alignment
                        -> kalign_alignment
    main_region     -- Main sub sequence region: [start, end]
    motif           -- Specify motif, not use start/end position
    
    Locate homologous region in multiple sequences
    
    Return { species_name1: seq1, species_name2: seq2,... }
    
    Require: muscle or kalign
    """
    
    if main_region is None and sub_seq is None:
        sys.stderr.writelines("Error: main_region and sub_seq must have a parameter\n")
        raise NameError("Error: main_region and sub_seq must have a parameter");
    
    if not sub_seq:
        sub_seq = seq_dict[main_id][main_region[0]-1:main_region[1]]
    
    species_list = seq_dict.keys()
    seq_list = [ seq_dict[k] for k in species_list ]
    align_seq = align_func(seq_list, verbose=False)
    align_dict = dict( zip(species_list, align_seq) )
    
    motif_align_dict = {}
    s, e = align_find(align_dict[main_id], sub_seq)
    if s != -1:
        for tid in align_dict:
            motif_align_dict[tid] = align_dict[tid][s-1:e]
        return motif_align_dict
    else:
        return None

def dot_to_alignDot(dot, aligned_seq):
    """
    dot                     -- Dotbracket structure
    aligned_seq             -- Aligned sequence  ATCGACG-ATAGCT-AATGCTAGC
    
    Convert dotbracket structure to aligned dotbracket structure
    """
    assert len(dot) == len(aligned_seq) - aligned_seq.count('-')
    
    alignedSS = ""
    i = 0
    for base in list(aligned_seq):
        if base == '-':
            alignedSS +=  '-'
        else:
            alignedSS += dot[i]
            i += 1
    return alignedSS

def shape_to_alignSHAPE(shape_list, aligned_seq):
    """
    shape_list              -- A list of shape scores
    aligned_seq             -- Aligned sequence  ATCGACG-ATAGCT-AATGCTAGC
    
    Convert shape list structure to aligned shape list
    """
    assert len(shape_list) == len(aligned_seq) - aligned_seq.count('-')
    
    alignedSHAPE = []
    i = 0
    for base in list(aligned_seq):
        if base == '-':
            alignedSHAPE.append('NULL')
        else:
            alignedSHAPE.append(shape_list[i])
            i += 1
    return alignedSHAPE

def annotate_covariation(ref_aligned_seq, input_aligned_seq, ref_aligned_dot, anno_loop=False):
    """
    ref_aligned_seq             -- Reference aligned sequence
    input_aligned_seq           -- An input aligned sequence to annotate
    ref_aligned_dot             -- Reference aligned dotbracket structure
    anno_loop                   -- Will annotate loop mutations
    
    Use color to annotate mutate bases in stem loop
    """
    
    import Colors
    
    assert len(ref_aligned_seq) == len(input_aligned_seq) == len(ref_aligned_dot)
    ref_aligned_seq = ref_aligned_seq.replace('U', 'T')
    input_aligned_seq = input_aligned_seq.replace('U', 'T')
    
    anno_align_seq = list(input_aligned_seq)
    
    pair_bps = [ 'AT', 'TA', 'CG', 'GC', 'TG', 'GT' ]
    
    bp_list = dot2ct(ref_aligned_dot)
    for bp in bp_list:
        raw_bp = ref_aligned_seq[ bp[0]-1 ]+ref_aligned_seq[ bp[1]-1 ]
        new_bp = input_aligned_seq[ bp[0]-1 ]+input_aligned_seq[ bp[1]-1 ]
        assert raw_bp in pair_bps
        if new_bp in pair_bps:
            if raw_bp != new_bp:
                anno_align_seq[ bp[0]-1 ] = Colors.f(anno_align_seq[ bp[0]-1 ], fc="cyan") #'\x1b[1;36;40m' + anno_align_seq[ bp[0]-1 ] + '\x1b[0m'
                anno_align_seq[ bp[1]-1 ] = Colors.f(anno_align_seq[ bp[1]-1 ], fc="cyan") #'\x1b[1;36;40m' + anno_align_seq[ bp[1]-1 ] + '\x1b[0m'
        else:
            anno_align_seq[ bp[0]-1 ] = Colors.f(anno_align_seq[ bp[0]-1 ], fc="red") #'\x1b[1;31;40m' + anno_align_seq[ bp[0]-1 ] + '\x1b[0m'
            anno_align_seq[ bp[1]-1 ] = Colors.f(anno_align_seq[ bp[1]-1 ], fc="red") #'\x1b[1;31;40m' + anno_align_seq[ bp[1]-1 ] + '\x1b[0m'
    
    if anno_loop:
        for i in range(len(anno_align_seq)):
            if ref_aligned_dot[i] == '.' and input_aligned_seq[i] != ref_aligned_seq[i]:
                anno_align_seq[ i ] = Colors.f(anno_align_seq[i], fc="yellow") #'\x1b[1;33;40m' + anno_align_seq[ i ] + '\x1b[0m'
    
    return "".join(anno_align_seq)

############################################
#######    Structure comparision
############################################

def correct_pair(pred_pair, true_pair, shift=1):
    """
    pred_pair           -- Predicted base pair (pos1, pos2)
    true_pair           -- True base pair (pos1, pos2)
    shift               -- Miximum shift
    """
    if abs(pred_pair[0]-true_pair[0])<=shift and pred_pair[1]==true_pair[1]:
        return True
    elif pred_pair[0]==true_pair[0] and abs(pred_pair[1]-true_pair[1])<=shift:
        return True
    return False

def dot_F1(pred_dot, true_dot, shift=1):
    """
    Compare predicted structure and true structure and calculate the F1 score

    pred_dot            -- Predicted dot-bracket structure
    true_dot            -- True dot-bracket structure
    shift               -- Miximum shift, shift=1 means that (i,j+1) and (i+1,j) are considered true
    
    Return F1 score
    """
    pred_ctlist = dot2ct(pred_dot)
    true_ctlist = dot2ct(true_dot)
    
    TP = FP = FN = 0
    for pred_pair in pred_ctlist:
        find = False
        for true_pair in true_ctlist:
            if correct_pair(pred_pair, true_pair, shift=shift):
                TP += 1
                find = True
                break
        if not find:
            FP += 1
    
    for true_pair in true_ctlist:
        find = False
        for pred_pair in pred_ctlist:
            if correct_pair(pred_pair, true_pair, shift=shift):
                find = True
                break
        if not find:
            FN += 1
    
    F1 = 2*TP/(2*TP+FP+FN)
    
    return F1