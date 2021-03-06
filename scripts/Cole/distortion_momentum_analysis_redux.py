# now using LHelix reconstruction
import os
import sys
import argparse
import time
import numpy as np
import pandas as pd
from tqdm import tqdm
from joblib import Parallel, delayed
import multiprocessing

# from emtracks.impact_param import *
from emtracks.particle import trajectory_solver
from emtracks.mapinterp import get_df_interp_func
from emtracks.Bdist import get_B_df_distorted

# directories
datadir = '/home/ckampa/data/pickles/distortions/linear_gradient/'

# set up B interpolators
ddir = '/home/shared_data/'
# fBnom = ddir+"Bmaps/Mau10/combined/Mau10_1.00xDS_1.00xPS-TS_DSMap.p"
# fBdis = ddir+"Bmaps/Mau10/combined/Mau10_1.00xDS_{0}xPS-TS_DSMap.p"
fBnom = ddir+"Bmaps/Mu2e_DSMap_V13.p"
# fBdis = ddir+"Bmaps/Mau13/subtracted/Mau13_1.00xDS_{0}xPS-TS_DSMap.p" # scale TS
fBdis = ddir+"Bmaps/Mau13/subtracted/Mau13_{0}xDS_{1}xPS-TS_DSMap.p" # scale DS

# scales for distorted fields
# scales_coarse = np.linspace(0., 0.9, 10) # first coarse fields, scale TS
scales_coarse = np.linspace(0.1, 0.9, 9) # first coarse fields, scale DS
scales_fine = np.concatenate([np.linspace(.91, .99, 9), np.linspace(1.01, 1.10,10)])# new fields
scales_finer = np.linspace(.995, 1.005, 11)
scales = np.concatenate([scales_coarse, scales_fine, scales_finer])# course fields + new fields
scales_str = [f'{scale:.2f}' if int(round(scale*1000 % 10)) == 0 else f'{scale:.3f}' for scale in scales]

#### Solenoid off
# fields = [f'{n:0.2f}' for n in scales] # which fields to analyze
fields = scales_str
TSs = ['1.00' if int(round(scale*1000 % 10)) == 0 else '1.000' for scale in scales]
B_Mu2e_nom = get_df_interp_func(fBnom, gauss=False)
B_Mu2e_dis_list = [get_df_interp_func(fBdis.format(field, TS), gauss=False) for field, TS in zip(fields, TSs)]
####

#### Linear Gradient
# df_Mu2e_nom = pd.read_pickle(fBnom)
# df_Mu2e_dis = get_B_df_distorted(df_Mu2e_nom, v="0")
# # B functions
# B_Mu2e_nom = get_df_interp_func(df=df_Mu2e_nom, gauss=False)#, bounds=bounds_Mu2e)
# B_Mu2e_dis = get_df_interp_func(df=df_Mu2e_dis, gauss=False)#, bounds=bounds_Mu2e)

# del(df_Mu2e_nom)
# del(df_Mu2e_dis)
####

# analyze a given track w nominal and distorted field
def analyze_particle_momentum(particle_num, name, outdir):
    # load track (pickle)
    fname = outdir+name+f'.{particle_num:03d}.pkl.nom.pkl'
    e_Mu2e = trajectory_solver.from_pickle(fname)
    # analyze
    # nominal
    e_Mu2e.B_func = B_Mu2e_nom
    e_Mu2e.analyze_trajectory_LHelix(step=100, stride=1)
    mom_nom = e_Mu2e.mom_LHelix
    # distorted
    mom_dis_list = []
    for B_Mu2e_dis in B_Mu2e_dis_list:
        e_Mu2e.B_func = B_Mu2e_dis
        e_Mu2e.analyze_trajectory_LHelix(step=100, stride=1)
        mom_dis_list.append(e_Mu2e.mom_LHelix)
    return mom_nom, mom_dis_list

# driving function
def run_analysis(name="run_04", outdir="/home/ckampa/data/pickles/distortions/linear_gradient/run_04/", N_lim=None):
    print("Start of Distortion LHelix Momentum Analysis")
    print("---------------------------___--------------")
    print(f"Directory: {outdir},\nFilename: {name}")
    start = time.time()
    df_run = pd.read_pickle(outdir+'MC_sample_plus_reco.pkl')
    num_cpu = multiprocessing.cpu_count()
    print(f"CPU Cores: {num_cpu}")
    base = outdir+name
    particle_nums = [int(f[7:10]) for f in sorted(os.listdir(datadir+'run_04/')) if "nom" in f]
    if N_lim is not None:
        particle_nums = particle_nums[:int(N_lim)]
        df_run = df_run.iloc[:int(N_lim)].copy()
        df_run.reset_index(drop=True, inplace=True)
    N = len(df_run)
    reco_tuples = Parallel(n_jobs=num_cpu)(delayed(analyze_particle_momentum)(num, name=name, outdir=outdir) for num in tqdm(particle_nums, file=sys.stdout, desc='particle #'))
    mom_noms = np.array([i[0] for i in reco_tuples])
    mom_diss = np.array([i[1] for i in reco_tuples])
    ###
    # results_dict = {f'mom_dis_{s:0.2f}TS': mom_diss[:,i] for i,s in enumerate(scales)}
    # results_dict = {f'mom_dis_{s:0.2f}DS': mom_diss[:,i] for i,s in enumerate(scales)}
    results_dict = {f'mom_dis_{s}DS': mom_diss[:,i] for i,s in enumerate(scales_str)}
    ###
    results_dict['mom_nom'] = mom_noms
    # save to dataframe
    for key, val in results_dict.items():
        df_run.loc[:, key] = val
    # df_run.to_pickle(outdir+'MC_sample_plus_reco_Mau10_TSOff.pkl') # Solenoid Off (Mau10 combination)
    # df_run.to_pickle(outdir+'MC_sample_plus_reco_Mau13_TSOff.pkl') # TS Solenoid Off (Mau13 subtraction)
    df_run.to_pickle(outdir+'MC_sample_plus_reco_Mau13_DSOff.pkl') # DS Solenoid Off (Mau13 subtraction)
    # df_run.to_pickle(outdir+'MC_sample_plus_reco_Mau13_DSOff_TEST.pkl') # Solenoid Off (Mau13 subtraction)
    # df_run.to_pickle(outdir+'MC_sample_plus_reco_Mau13_TSOff_TEST.pkl') # Solenoid Off (Mau13 subtraction)
    stop = time.time()
    print("Calculations Complete")
    print(f"Runtime: {stop-start} s, {(stop-start)/60.} min, {(stop-start)/60./60.} hr")
    print(f"Speed: {(stop-start) / (2*N)} s / trajectory")
    return

if __name__=='__main__':
    # parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--directory', help='Output directory')
    parser.add_argument('-f', '--filename', help='Output base filename')
    parser.add_argument('-N', '--number', help='Number of events')
    args = parser.parse_args()
    # fill defaults where needed
    if args.directory is None:
        args.directory = "/home/ckampa/data/pickles/distortions/linear_gradient/testing/"
    if args.filename is None:
        args.filename = "test_01"
    # run
    run_analysis(name=args.filename, outdir=args.directory, N_lim=args.number)
