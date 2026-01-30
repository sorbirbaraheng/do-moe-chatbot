import React, { useState, useEffect } from 'react';
import { db } from '../../../services/firebase';
import { collection, getDocs, doc, updateDoc, query, orderBy, limit } from 'firebase/firestore';

interface UserData {
    id: string;
    email: string;
    displayName: string;
    photoURL?: string;
    role: 'user' | 'admin';
    status?: 'active' | 'banned';
    note?: string;
    createdAt?: string;
}

const UserManagementTab: React.FC = () => {
    const [users, setUsers] = useState<UserData[]>([]);
    const [filteredUsers, setFilteredUsers] = useState<UserData[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterRole, setFilterRole] = useState<'all' | 'admin' | 'user'>('all');
    const [statusMsg, setStatusMsg] = useState('');

    useEffect(() => {
        fetchUsers();
    }, []);

    // Filter logic
    useEffect(() => {
        let result = users;

        if (searchTerm) {
            const lowerTerm = searchTerm.toLowerCase();
            result = result.filter(u =>
                u.email.toLowerCase().includes(lowerTerm) ||
                u.displayName?.toLowerCase().includes(lowerTerm)
            );
        }

        if (filterRole !== 'all') {
            result = result.filter(u => u.role === filterRole);
        }

        setFilteredUsers(result);
    }, [users, searchTerm, filterRole]);

    const fetchUsers = async () => {
        setLoading(true);
        try {
            // DEBUG: Simplify query to test basic connectivity
            // const q = query(collection(db, 'users'), orderBy('createdAt', 'desc'), limit(100));
            const q = query(collection(db, 'users'), limit(50));

            const querySnapshot = await getDocs(q);

            const fetchedUsers: UserData[] = [];
            querySnapshot.forEach((doc) => {
                const data = doc.data();
                // Ensure required fields exist
                fetchedUsers.push({
                    id: doc.id,
                    email: data.email || 'No Email',
                    displayName: data.displayName || 'No Name',
                    role: data.role || 'user', // Default to user if missing
                    photoURL: data.photoURL,
                    status: data.status,
                    createdAt: data.createdAt
                } as UserData);
            });

            console.log("✅ Fetched users:", fetchedUsers.length);
            setUsers(fetchedUsers);
            setStatusMsg(''); // Clear any previous error
        } catch (error: any) {
            console.error("Error fetching users:", error);
            console.error("Error code:", error.code);
            console.error("Error message:", error.message);
            setStatusMsg(`❌ Error: ${error.message} (${error.code})`);
        } finally {
            setLoading(false);
        }
    };

    const handleRoleChange = async (userId: string, newRole: 'user' | 'admin') => {
        try {
            await updateDoc(doc(db, 'users', userId), { role: newRole });

            // Optimistic update
            setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: newRole } : u));
            setStatusMsg(`✅ Role updated to ${newRole}`);
            setTimeout(() => setStatusMsg(''), 3000);
        } catch (error) {
            console.error("Error updating role:", error);
            setStatusMsg('❌ Failed to update role');
        }
    };

    const handleBanToggle = async (userId: string, currentStatus: string = 'active') => {
        const newStatus = currentStatus === 'banned' ? 'active' : 'banned';
        try {
            await updateDoc(doc(db, 'users', userId), { status: newStatus });

            // Optimistic update
            setUsers(prev => prev.map(u => u.id === userId ? { ...u, status: newStatus } : u));
            setStatusMsg(`✅ User ${newStatus === 'banned' ? 'Banned' : 'Activated'}`);
            setTimeout(() => setStatusMsg(''), 3000);
        } catch (error) {
            console.error("Error updating status:", error);
            setStatusMsg('❌ Failed to update status');
        }
    };

    return (
        <div className="space-y-6">
            {/* Header Controls */}
            <div className="flex flex-col md:flex-row gap-4 justify-between items-center bg-white p-4 rounded-2xl border border-black/5 shadow-sm">
                <div className="relative w-full md:w-96">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
                    </svg>
                    <input
                        type="text"
                        placeholder="ค้นหาชื่อ หรือ Email..."
                        className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>

                <div className="flex gap-2">
                    <select
                        className="px-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm font-medium focus:outline-none"
                        value={filterRole}
                        onChange={(e) => setFilterRole(e.target.value as any)}
                    >
                        <option value="all">All Roles</option>
                        <option value="admin">Admin</option>
                        <option value="user">User</option>
                    </select>

                    <button
                        onClick={fetchUsers}
                        className="p-2 text-gray-600 hover:bg-gray-100 rounded-xl transition-all"
                        title="Refresh"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
                        </svg>
                    </button>
                </div>
            </div>

            {statusMsg && (
                <div className="text-center text-sm font-medium text-blue-600 bg-blue-50 py-2 rounded-lg animate-in fade-in">
                    {statusMsg}
                </div>
            )}

            {/* User Table */}
            <div className="bg-white rounded-2xl border border-black/5 shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-gray-50/50 border-b border-gray-100">
                            <tr>
                                <th className="px-6 py-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">User Profile</th>
                                <th className="px-6 py-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">Role</th>
                                <th className="px-6 py-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">Status</th>
                                <th className="px-6 py-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">Registered</th>
                                <th className="px-6 py-4 text-xs font-semibold text-gray-400 uppercase tracking-wider text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {loading ? (
                                <tr>
                                    <td colSpan={5} className="px-6 py-12 text-center text-gray-400">
                                        Loading users...
                                    </td>
                                </tr>
                            ) : filteredUsers.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="px-6 py-12 text-center text-gray-400">
                                        No users found matching your criteria.
                                    </td>
                                </tr>
                            ) : (
                                filteredUsers.map((user) => (
                                    <tr key={user.id} className="hover:bg-gray-50/50 transition-colors group">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                {user.photoURL ? (
                                                    <img src={user.photoURL} alt="" className="w-10 h-10 rounded-full object-cover border border-gray-100" />
                                                ) : (
                                                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center text-blue-600 font-bold text-sm">
                                                        {user.email.charAt(0).toUpperCase()}
                                                    </div>
                                                )}
                                                <div>
                                                    <div className="font-medium text-[#1D1D1F]">{user.displayName || 'No Name'}</div>
                                                    <div className="text-xs text-gray-400">{user.email}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${user.role === 'admin'
                                                ? 'bg-purple-50 text-purple-700 border-purple-100'
                                                : 'bg-blue-50 text-blue-700 border-blue-100'
                                                }`}>
                                                {user.role === 'admin' && '⚡'}
                                                {user.role.toUpperCase()}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${user.status === 'banned'
                                                ? 'bg-red-50 text-red-600'
                                                : 'bg-green-50 text-green-600'
                                                }`}>
                                                {user.status === 'banned' ? 'Banned' : 'Active'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-500">
                                            {user.createdAt ? new Date(user.createdAt).toLocaleDateString('th-TH') : '-'}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                {/* Role Toggle */}
                                                <button
                                                    onClick={() => handleRoleChange(user.id, user.role === 'admin' ? 'user' : 'admin')}
                                                    className="p-2 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-purple-600 transition-colors"
                                                    title={user.role === 'admin' ? 'Demote to User' : 'Promote to Admin'}
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
                                                    </svg>
                                                </button>

                                                {/* Ban Toggle */}
                                                <button
                                                    onClick={() => handleBanToggle(user.id, user.status)}
                                                    className={`p-2 hover:bg-gray-100 rounded-lg transition-colors ${user.status === 'banned' ? 'text-green-600 hover:bg-green-50' : 'text-gray-500 hover:text-red-600 hover:bg-red-50'
                                                        }`}
                                                    title={user.status === 'banned' ? 'Unban User' : 'Ban User'}
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 0 0 5.636 5.636m12.728 12.728A9 9 0 0 1 5.636 5.636m12.728 12.728L5.636 5.636" />
                                                    </svg>
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="text-center text-xs text-black/30">
                Showing recent 100 users. Search to find specific users.
            </div>
        </div>
    );
};

export default UserManagementTab;
