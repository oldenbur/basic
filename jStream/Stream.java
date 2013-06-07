import java.io.*;
import java.util.*;

public class Stream{
	
	protected Hashtable<Integer,Job> _jobs		= new Hashtable<Integer,Job>();		//  all jobs by id
	protected Hashtable<Integer,Job> _targets	= new Hashtable<Integer,Job>();		//  all current targets by id
	protected Hashtable<Integer,Job> _dummies	= new Hashtable<Integer,Job>();		//  all dummy jobs by id
	
	public static boolean _debug		= false;		//  print debug messages
	public static boolean _streamPrint	= false;		//  print stream jobs as they are built
	public static String _strTab		= "  ";			//  tab string for formatting stream printing
	
	/**
	 * Print the program usage statement and exit with the specified status.
	 * @param status exit status
	 */
	public static void usage(int status){
		System.out.println("usage: java Stream {input_csv}");
		System.exit(status);
	}
	
	/**
	 * Assumes that the input list contains a single parameter, which is the name of a
	 * job data file to process.  The file is opened for reading, and line-by-line, jobs
	 * are parsed and added to the _jobs and _targets datastructures by the function
	 * addJob().  Once the file parsing is complete, the targets are sorted and then
	 * each is passed to buildStream(), which collects all jobs in the stream, and then
	 * the results are printed.  
	 * @param args command-line input containing input file
	 */
	public static void main(String[] args){
		
		//  verify the number of input arguments
		if( 1 > args.length ) usage(0);
		for(int i=1; i < args.length; i++)
			System.out.println("WARNING: ignoring input '" + args[i] + "'");
		
		//  verify the input file
		File fInput = new File(args[0]);
		if( !fInput.exists() ){
			System.out.println("ERROR: input file '" + args[0] + "' does not exist");
			usage(1);
		}
		else if( !fInput.isFile() ){
			System.out.println("ERROR: input file '" + args[0] + "' is not a file");
			usage(1);
		}
		
		//  open and parse the file
		Stream stream = new Stream();
		int intLine = 0;
		try{
			BufferedReader reader = new BufferedReader( new FileReader(fInput) );
			
			//  hand each line off to addJob()
			while( reader.ready() ){
				String strLine = reader.readLine();
				intLine++;
				if( strLine.startsWith("Id") ) continue;
				if( !stream.addJob(strLine) ){
					System.out.println("ERROR: failed to parse job on line: " + intLine);
					System.exit(1);
				}
			}
			
			reader.close();
			
		} catch(IOException ioe){
			System.out.println("ERROR: caught IOException parsing input file '" + args[0] + "'" +
								(0 < intLine ? "  line: " + intLine : ""));
			ioe.printStackTrace();
		}
		
		//  print a parsing report
		if( _debug ) 
			System.out.println("Parsing complete\n" +
			   		   		   "  #   lines: " + intLine + "\n" +
					   		   "  #    jobs: " + stream._jobs.size() + "\n" + 
					   		   "  # targets: " + stream._targets.size() + "\n" +
					   		   "  # dummies: " + stream._dummies.size() + "\n");

		/*
		 *  build the list of targets by brute force - that is make a copy of the jobs
		 *    list and then go through each job's predecessors and group members removing
		 *    them from the list - this was used to check (and fix) the built-on-the-fly
		 *    data structure, _targets.  I think this method is less efficient, though.
		 *    
		
		Hashtable<Integer,Job> targets = new Hashtable<Integer,Job>();
		for(Integer id : stream._jobs.keySet()) targets.put(id, stream._jobs.get(id));
		for(Job t : stream._jobs.values()){
			for(Job p : t._predecessors) targets.remove(p._id);
			for(Job g : t._group)        targets.remove(g._id); 
		}
		
		//  sort and print the list of targets
		TreeSet<Job> sorted_test = new TreeSet<Job>(new Comparator<Job>(){
			public int compare(Job o1, Job o2) { return o1._name.compareTo( o2._name ); }
		});
		sorted_test.addAll(targets.values());		
		for(Job j : sorted_test) System.out.println(j._name);
		System.out.println("total targets: " + sorted_test.size() + "\n");
		
		 *
		 */
		
		//  sort and print the list of targets
		TreeSet<Job> sorted = new TreeSet<Job>(new Comparator<Job>(){
			public int compare(Job o1, Job o2) { return o1._name.compareTo( o2._name ); }
		});
		sorted.addAll(stream._targets.values());
		
		//  build a stream for each target
		int intStreamedJobs = 0;
		Hashtable<Integer,Job> streamedJobs	= new Hashtable<Integer,Job>();		
		for(Job j : sorted){
			Hashtable<Integer,Job> s = new Hashtable<Integer,Job>();	
			stream.buildStream(j, s);
			System.out.printf("%14s: %7d\n", j._name, s.size());
			if( _streamPrint ) System.out.println("\n");
			if( _debug ){
				intStreamedJobs += s.size();
				for(Integer id : s.keySet()) streamedJobs.put(id, s.get(id));
			}
		}

		//  post-analysis
		if( _debug ){
			
			//  find jobs that were not included in any stream - a sign of a bug
			ArrayList<Job> listMissing = new ArrayList<Job>();
			for(Integer id : stream._jobs.keySet()){
				if( !streamedJobs.containsKey(id) ) listMissing.add(stream._jobs.get(id));
			}
			if( 0 < listMissing.size() ){
				System.out.println("\nWARNING: Missing jobs:");
				for(Job j : listMissing) System.out.println(j);
				System.out.println();
			}
			
			//  print a post-processing report
			System.out.println("\n" +
					"  #            jobs: " + stream._jobs.size() + "\n" + 
					"  #   streamed_jobs: " + intStreamedJobs + "\n" +
					"  # unstreamed_jobs: " + listMissing.size());		

		}
		
	}
	
	/**
	 * Parse the input job data file line and build a {@link Job} structure containing
	 * the parsed job information.  If the parsing is successful, the job is added to 
	 * Hashtable _jobs using its id as the key.  Returns true on success, false
	 * otherwise.  If parsing fails, an error message is printed with details.
	 * @param line the job data file to parse and build a <i>Job</i> for
	 * @return true if the parsing was successful, false otherwise
	 */
	public boolean addJob(String line){
		
		//  split the line into tokens and verify the number of them
		String[] tokens = line.split(",");
		if( 3 > tokens.length ){
			System.out.println("ERROR: unexpected number of tokens in job line: '" + line + "'");
			return false;
		}
				
		//  parse and verify the job id
		Integer intId = new Integer(tokens[0]);
		
		//  look to see if the job has already been created
		Job job	= new Job();
		if( _jobs.containsKey(intId) ){
			job = _jobs.get(intId);
			//if( _debug ) System.out.println("WARNING: found existing job for new job named '" + tokens[2] + "':\n  " + job);
		}
		
		//  build the job
		job._line	= line;
		job._id		= intId;
		job._type	= jobTypeCode(tokens[1]);
		job._name	= tokens[2];
				
		//  check that the parent group exists, creating a dummy if not
		Job parent = null;
		if( 3 < tokens.length && !"".equals(tokens[3]) ){
			Integer intParentId = new Integer(tokens[3]);
			if( !_jobs.containsKey(intParentId) ){
				//if( _debug ) System.out.println("WARNING: no parent with id " + intParentId + " found for job with id " + intId);
				parent = new Job();
				parent._id = intParentId;
				parent._type = TYPE_GROUP;
				_jobs.put(intParentId, parent);
				_targets.put(intParentId, parent);
				_dummies.put(intParentId, parent);
			} else {
				parent = _jobs.get(intParentId);
			}
			
			//  verify that the parent is a group
			if( parent._type != TYPE_GROUP ){
				System.out.println("ERROR: parent with id " + intParentId + " has invalid type " + 
									jobTypeString(parent._type) + " for job with id " + intId);
				return false;
			}
		}
		
		//  set the jobs parent, add it to the parents group and remove it as a target
		job._parent	= parent;
		if( null != parent ){
			parent._group.add(job);
			_targets.remove(job._id);
		}
		
		//  add the job's predecessors
		for(int i=4; i < tokens.length; i++){
			
			//  find the predecessor and add it
			Job pred = null;
			Integer intPredId = new Integer(tokens[i]);
			if( !_jobs.containsKey(new Integer(intPredId)) ){
				//if( _debug ) System.out.println("WARNING: no predecessor with id " + intPredId + " found for job with id " + intId);
				pred = new Job();
				pred._id = intPredId;
				pred._predDummy = true;
				_jobs.put(intPredId, pred);
				_dummies.put(intPredId, pred);
			} else {
				pred = _jobs.get(intPredId);
			}
			job._predecessors.add(pred);
			
			//  remove the predecessor from the targets map
			_targets.remove(intPredId);
		}

		//  add the job to the jobs map
		_jobs.put(intId, job);
		_dummies.remove(intId);
		
		//  if the job has no parent and is not a predecessor, it is currently a target
		if( null == job._parent && !job._predDummy ) _targets.put(intId, job);
		
		return true;
	}
	
	
	/**
	 * Build a stream starting at the input target, its parent if appropriate and all 
	 * of its predecessors and members in a recursive manner. 
	 * @param target  the job from which the stream will be built
	 * @param stream  stream table to add jobs to
	 * @param tab     (optional) formatting tab width for debug printing
	 */
	public void buildStream(Job target, Hashtable<Integer,Job> stream, String tab){

		//  if the current job is already present and is of type job, don't add it
		if( stream.containsKey(target._id) && target._type == TYPE_JOB ) return;

		//  add the current job to the stream
		stream.put(target._id, target);
		if( _streamPrint ) System.out.println(tab + target);
		
		//  if the target is a group, add its members, recursively
		for(Job group : target._group) buildStream(group, stream, tab + _strTab);
		
		//  add the target's predecessors to the stream, recursively
		for(Job pred : target._predecessors) buildStream(pred, stream, tab + _strTab);
		
		buildStreamParent(target._parent, stream, _strTab);
	}
	public void buildStream(Job target, Hashtable<Integer,Job> stream){
		buildStream(target, stream, "");
	}
	
	/**
	 * Assume that the input job is a parent of a job in the stream.  Add the parent job
	 * and all its predecessors recursively to the stream, then recursively add its parent.
	 * @param target  the job from which the stream will be built
	 * @param stream  stream table to add jobs to
	 * @param tab     (optional) formatting tab width for debug printing
	 */
	public void buildStreamParent(Job target, Hashtable<Integer,Job> stream, String tab){
		
		//  do nothing if there is no parent or it is already present
		if( null == target || stream.containsKey(target._id) ) return;
		
		//  add the parent to the stream
		stream.put(target._id, target);
		if( _streamPrint ) System.out.println(tab + target);

		//  add the parent's predecessors to the stream, recursively
		for(Job pred : target._predecessors) buildStream(pred, stream, tab + _strTab);

		//  recursively add the parent's parent
		buildStreamParent(target._parent, stream, tab + _strTab);
	}
	
	//  enum for denoting job type - see: Job._type, Stream.jobTypeString() and Stream.jobTypeCode()
	public static final int TYPE_NONE	= 0;
	public static final int TYPE_GROUP	= 1;
	public static final int TYPE_JOB	= 2;
	
	/**
	 * Build a String that reflects the input job type enum value
	 * @param type job type enum value
	 * @return the <i>String</i> representation of the input job type
	 */
	public static String jobTypeString(int type){
		switch(type){
		case TYPE_NONE:		return "none";
		case TYPE_GROUP:	return "group";
		case TYPE_JOB:		return "job";
		default:			return "???";
		}
	}

	/**
	 * Parse the input job type, which is expected to be either 'job' or 'group' and
	 * return the corresponding type code: TYPE_JOB or TYPE_GROUP.  If the job type
	 * cannot be parsed, an error is printed and TYPE_NONE is returned.
	 * @param type the <i>String</i> containing the jobe type
	 * @return the code the corresponds to the input job type
	 */
	public static int jobTypeCode(String type){
		if     ( type.equals("job")   )	return TYPE_JOB;
		else if( type.equals("group") )	return TYPE_GROUP;
		else{
			System.out.println("WARNING: failed to parse job type code: '" + type + "'");
			return TYPE_NONE;
		}
	}
	
	/**
	 * The Job class is a struct-like container for the information that constitutes a
	 * single job or group.  It corresponds to a single line of an input csv job data
	 * file.
	 * @author pgoldenb
	 */
	class Job{
		
		public String			_line			= "";
		public Integer			_id				= -1;
		public int				_type			= TYPE_NONE;
		public String			_name			= "";
		public Job				_parent 		= null;
		public ArrayList<Job>	_predecessors	= new ArrayList<Job>();
		public ArrayList<Job>	_group			= new ArrayList<Job>();
		public boolean			_predDummy		= false;
		
		/**
		 * Build and return a fixed-width String representation of the job, although not
		 * a complete serialization because prececessors information is not included.
		 * @return the <i>String</i> containing information about the the serialized 
		 */
		public String toString(){
			return String.format("[ name: %-12s  id: %6d  type: %-5s  parent: %-12s  #pred: %3d  " +
								    "#group: %3d  pred_dummy: %s ]",
									_name, _id, jobTypeString(_type), 
									(null != _parent ? _parent._name : "(none)"),
									_predecessors.size(), _group.size(), _predDummy);
		}
		
	}
	
}
