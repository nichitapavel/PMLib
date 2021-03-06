/*
 * device.cpp
 *
 * Created on: 27/05/2016
 *
 * =========================================================================
 *  Copyright (C) 2016-, Manuel F. Dolz (maneldz@gmail.com)
 *
 *  This file is part of PMLib.
 *
 *  PMLib is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  PMLib is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this PMLib.  If not, see <http://www.gnu.org/licenses/>.
 *
 * =========================================================================
*/

#include <ctime>
#include <iostream>
#include <thread>
#include <atomic>
#include <boost/thread.hpp>

#include "device.hpp"
#include "server.hpp" 
#include "counter.hpp"
#include "utils/logger.hpp"

namespace PMLib {

map_type *Device::device_register;

Device::Device(string name, string url, int max_freq, int n_lines, bool pdu, function<void()> readf) : 
    _name{name}, _url{url}, _max_frequency{max_freq}, _n_lines{n_lines}, _pdu{pdu}, the_thread(), 
    _working{false}, _running{true}, _readf{readf}, sample(n_lines, 0), data_queue() {}

Device::~Device() {
    _running = false;
    if( the_thread.joinable() ) 
        the_thread.join();
}

shared_ptr<Device> Device::create_device(string type, string name, string url) {
    auto it = get_map()->find(type);
    return (it == get_map()->end()) ? nullptr : it->second(name, url);
}

void Device::register_counter(const Counter &c) { 
    counter_lock.lock();
    counter_map[c.get_id()] = make_shared<Counter>(c);    
    for (auto &l : c.get_lines()) {
        lines[l]->enable();
    }
    counter_lock.unlock();
}

void Device::deregister_counter(const Counter &c) { 
    counter_lock.lock();
    auto it = counter_map.find( c.get_id() );
    if ( it != counter_map.end() ) {
        for (auto &l : c.get_lines()) {
            lines[l]->disable();
            if ( !lines[l]->is_enabled() )
                lines[l]->clear_data();
        }
        counter_map.erase(c.get_id());
    }
    counter_lock.unlock();
}

void Device::register_line(string name, string description, string metric, int number, Computer &c, float voltage,
    float offset, float slope) {
    // Map string metrics to enum.
    std:map<std::string, Metric> avail_metrics 
    {
      { "voltage" , Metric::voltage },
      { "shunt_voltage" , Metric::shunt_voltage },
      { "current" , Metric::current },
      { "power" , Metric::power },
      { "temperature" , Metric::temperature },
      { "default" , Metric::def }
    };

    Metric _metric;

    try
    {
      _metric = avail_metrics.at( metric );
    }
    catch( out_of_range )
    {
      std::cout << "Unavailable metric" << std::endl;
    }

    lines[number] = make_shared<Line>(name, description, _metric, number, voltage, c, offset, slope);
}

void Device::push_back_data(vector<double> &sample) {
    for (auto const &l : lines) {
        if ( l.second->is_active() ) {
            l.second->push_back_data( sample[l.first] );
        }
    }
}

void Device::get_lines_sizes(const vector<int> &sel_lines, set_t &sizes) {
    sizes.clear();
    for (auto const &l : sel_lines) {
        sizes[l] = lines[l]->get_size();
    }
}

const vector_type& Device::get_line_data(int l) {
    return lines[l]->get_data();
}

void Device::start_counter(const vector<int> &sel_lines) {
    counter_lock.lock();
    for (auto const &l : sel_lines) {
        lines[l]->activate();
    }
    counter_lock.unlock();
}

void Device::stop_counter(const vector<int> &sel_lines) {
    counter_lock.lock();
    for (auto const &l : sel_lines) {
        lines[l]->deactivate();
    }
    counter_lock.unlock();
}

void Device::start() {
    // This will start the thread. Notice move semantics!
    the_thread = thread( &Device::run, this );
}

void Device::stop() {
    _running.store(false);
}

void Device::run() {
    
    if (lines.size() < _n_lines) {
        start_cv.notify_all();
        return;
    }

    vector<double> _sample;
/*
    std::thread avg_thr( [&] () {

        vector<double> s;
        boost::circular_buffer<vector<double>> cb(_max_frequency);
        vector<double> avg_1m, avg_30s, avg_10s, avg_1s;
     //   int avg_1m_first, , avg_30s, avg_10s, avg_1s;

        while ( is_running() ) {
            while( !avg_queue.empty() && is_running() ) {
                while( !avg_queue.pop( s ) );
                cb.push_back(s);
                for ( auto &v : cb )
                    for ( auto &vi : v)
                        
            }
            // This is important as it avoids a full busy-wait loop!
            this_thread::sleep_for(chrono::microseconds((int)(1e6/_max_frequency)));
        }        

    } );
*/
    std::thread read_thr( [&] () {
        try { 
            _readf();
        }
        catch (std::exception& e) {
            CLOG_ERROR << "Error starting the device: " << e.what() << endl;
            cerr << "Error starting the device: " << e.what() << endl;
        }
    } );

    while ( is_running() ) {
        while( !data_queue.empty() && is_running() ) {
            while( !data_queue.pop( _sample ) );
            push_back_data(_sample);
//            avg_queue.push( _sample ); 
           // for ( auto &v: sample_) cout << v << " "; cout << endl;        
            if ( !is_working() ) {
                _working.store(true);
                start_cv.notify_all();
            }
        }
        // This is important as it avoids a full busy-wait loop!
        this_thread::sleep_for(chrono::microseconds((int)(1e6/_max_frequency)));
    }

//    avg_thr.join();
    read_thr.join();

    /* Old version with coroutines
    for (auto &sample : generator_t(_readf) ) {
        if ( !is_working() ) {
            _working.store(true);
            start_cv.notify_all();
        }
        push_back_data(sample);
    }
    */

    stop_cv.notify_all();

}

// end namespace PMLib
}
