import os, sys, argparse
import cantera as ct
os.environ['Cantera_Data'] =os.getcwd()

from create_trimmed_model import trim
from convert_chemkin_file import convert
from soln2cti import write
from autoignition_module import run_sim
from get_rate_data import get_rates
from drg import make_graph


def readin(args='none', **argv):
    """Main function for pyMARS

    Arguments
        file: Input mechanism file (ex. file='gri30.cti')
        species: Species to eliminate (ex. species='H, OH')
        thermo: Thermo data file if Chemkin format (ex. thermo= 'thermo.dat')
        transport: Transport data file if Chemkin format
        plot: plot ignition curve (ex. plot='y')
        points: print ignition point and sample range (ex. points='y')
        writecsv: write data to csv (ex. writecsv='y')
        writehdf5: write data to hdf5 (ex. writehdf5='y')
        run_drg: run DRG

    ----------
    Returns
        Converted mechanism file
        Trimmed Solution Object
        Trimmed Mechanism file
    ----------
    Example
        readin(file='gri30.cti', plot='y', species='OH, H')
    """

    "--------------------------------------------------------------------------"
    "--------------------------------------------------------------------------"

    class args():
        #direct use case
            if args is 'none':
                argparse.Namespace()
                plot = False
                points = False
                writecsv = False
                writehdf5 = False
                data_file = argv['file']
                thermo_file = None
                transport_file = None
                run_drg = None
                initial_sim = True
                iterate = False

                if 'thermo' in argv:
                    thermo_file = argv['thermo']
                if 'transport' in argv:
                    transport_file = argv['transport']
                if 'species' in argv:
                    species = argv['species']
                    exclusion_list = [str(item) for item in species.split(',')]
                    #strip spaces
                    for i, sp in enumerate(exclusion_list):
                        exclusion_list[i]=sp.strip()
                if 'species' not in argv:
                    exclusion_list=[]
                if 'plot' in argv:
                    plot = True
                if 'writecsv' in argv:
                    writecsv = True
                if 'writehdf5' in argv:
                    writehdf5 = True
                if 'points' in argv:
                    points = True
                if 'run_drg' in argv:
                    run_drg = True
                if 'iterate' in argv:
                    iterate = True
                x ='arg_none'

        #package from terminal use case
            if args is not 'none':
                plot = args.plot
                points = args.points
                writecsv = args.writecsv
                writehdf5 = args.writehdf5
                data_file= args.file
                thermo_file = args.thermo
                transport_file=args.transport
                run_drg=args.run_drg
                initial_sim = True
                iterate = args.iterate
                if args.species is None:
                    exclusion_list=[]
                else:
                    exclusion_list=[str(item) for item in args.species.split(',')]
                    #strip spaces
                    for i, sp in enumerate(exclusion_list):
                        exclusion_list[i]=sp.strip()
                x='args_not_none'


    ext= os.path.splitext(args.data_file)[1]

    if ext == ".cti" or ext == ".xml":
        print("\n\nThis is an Cantera xml or cti file\n")
        solution_object=ct.Solution(args.data_file)
        #trims file
        #need case if no trim necessary
        solution_objects=trim(solution_object, args.exclusion_list, args.data_file)
        if args.run_drg is False:
            trimmed_file=write(solution_objects[1])
        if args.plot is True or args.writecsv is True or args.points is True or args.writehdf5 is True:
            print 'running sim'
            sim_result=run_sim(solution_object, args)

        if args.run_drg is True:
            #get user input
            target_species = str(raw_input('Enter target starting species: '))
            #run first sim
            args.initial_sim = True
            sim_result_1=run_sim(solution_object, args)
            #retain sim initial conditions
            tau1=sim_result_1.tau
            args.frac=sim_result_1.frac
            args.Temp=sim_result_1.Temp
            get_rates('mass_fractions.hdf5', solution_object)
            args.initial_sim = False

            if args.iterate is True:
                print 'iterate is true'
                #set initial 0 cases
                error = 0.0
                threshold = 0.00
                loop_number = 0
                error_limit = float(raw_input('Acceptable Error Limit: '))
                while error < error_limit:
                    loop_number += 1
                    threshold +=.05
                    #run DRG
                    drg_exclusion_list = make_graph(solution_object, 'production_rates.hdf5', threshold, target_species)
                    new_solution_objects = trim(solution_object, drg_exclusion_list, args.data_file)
                    #run second sim
                    sim_result_2 = run_sim(new_solution_objects[1], args)
                    #compare error
                    tau2 = sim_result_2.tau
                    #print 'original ignition delay: ' + str(tau1)
                    #print 'new ignition delay: ' + str(tau2)
                    error = float((abs((tau1-tau2)/tau1))*100.0)
                    print 'error: ' + str(error) + ' %'
                    #print 'Loop number: ' + str(loop_number)
                print 'Number of loops: %s' %loop_number
                print 'Final max threshold value: %s' %threshold
                print 'Error: %s ' %error
            else:
                threshold = float(raw_input('Enter threshold value: '))
                drg_exclusion_list = make_graph(solution_object, 'production_rates.hdf5', threshold, target_species)
                new_solution_objects = trim(solution_object, drg_exclusion_list, args.data_file)
                #run second sim
                args.initial_sim = False
                sim_result_2 = run_sim(new_solution_objects[1], args)
                #compare error
                tau2 = sim_result_2.tau
                #print 'original ignition delay: ' + str(tau1)
                #print 'new ignition delay: ' + str(tau2)
                error = float(abs((tau1-tau2)/tau1))
                print 'error: ' + str(error) + ' %'
            n_species_eliminated = len(solution_object.species())-len(new_solution_objects[1].species())
            print 'Number of species eliminated: %s' %n_species_eliminated
            drg_trimmed_file = write(new_solution_objects[1])

    elif ext == ".inp" or ext == ".dat" or ext == ".txt":
        print("\n\nThis is a Chemkin file")
        #convert file to cti
        converted_file_name = convert(args.data_file, args.thermo_file, args.transport_file)
        #trims newly converted file
        solution_objects=trim(converted_file_name, args.exclusion_list)
        trimmed_file=write(solution_objects[1])

        if "plot" or "points" or "writecsv" or "writehdf5" in args:
            print 'running sim'
            run_sim(converted_file_name, args)

        if 'run_drg' in args:
            print 'running sim'
            run_sim(converted_file_name, args)
            get_rates('mass_fractions.hdf5', converted_file_name)
            print 'running DRG'
            drg_exclusion_list=make_graph(converted_file_name, 'production_rates.hdf5')
            new_solution_objects=trim(converted_file_name, drg_exclusion_list)
            args.data_file=write(new_solution_objects[1])

        #run_sim(converted_file_name, args)


    else:
        print("\n\nFile type not supported")
